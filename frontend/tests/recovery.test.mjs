import assert from "node:assert/strict";
import {createHash} from "node:crypto";
import {test} from "node:test";
import {runInContext} from "node:vm";
import {flush, harness} from "./harness.mjs";

const rootHash = "a".repeat(64);
const dependencyHash = "b".repeat(64);
const jobId = `job-${"c".repeat(32)}`;

function report(status = "READY") {
  const verified = status === "READY";
  return {
    schema_version: "forgegate.workspace-recovery-readiness.v1",
    backup_sha256: rootHash,
    manifest_fingerprint: `sha256:${"d".repeat(64)}`,
    checked_at: "2026-09-07T12:00:00Z",
    status,
    archived_job_count: 1,
    dependencies: [{
      backup_sha256: dependencyHash,
      job_ids: [jobId],
      status: verified ? "VERIFIED" : "FAILED",
      error_code: verified ? null : "RECOVERY_JOB_MISMATCH",
      result_payloads_verified: verified ? 1 : 0,
      jobs_without_result: 0
    }],
    scope: "snapshot_and_exact_archived_job_payloads",
    availability: "observed_during_check_only",
    restore: "NOT_PERFORMED",
    producer_authenticity: "NOT_VERIFIED",
    external_identity_and_artifact_files: "NOT_CHECKED"
  };
}

function handoff(sourceHash, status = "READY") {
  const ready = status === "READY";
  return {
    schema_version: "forgegate.recovery-readiness-handoff.v1",
    handoff_id: `sha256:${"e".repeat(64)}`,
    source_report_sha256: sourceHash,
    report_fingerprint: `sha256:${"f".repeat(64)}`,
    disposition: ready ? "READY_FOR_REHEARSAL" : "BLOCKED",
    readiness: report(status),
    dependency_count: 1,
    verified_dependency_count: ready ? 1 : 0,
    result_payloads_verified: ready ? 1 : 0,
    jobs_without_result: 0,
    payload_transfer: "NOT_INCLUDED",
    live_availability: "NOT_CHECKED",
    restore: "NOT_PERFORMED"
  };
}

function rehearsalReceipt() {
  const reviewedHandoff = handoff("1".repeat(64));
  return {
    schema_version: "forgegate.recovery-rehearsal.v1",
    rehearsal_id: `sha256:${"2".repeat(64)}`,
    handoff_sha256: "3".repeat(64),
    handoff: reviewedHandoff,
    completed_at: "2026-09-08T00:45:59Z",
    candidate_store: {sha256: "4".repeat(64), size_bytes: 225280},
    job_store: {sha256: "5".repeat(64), size_bytes: 118784},
    post_restore_job_count: 27,
    post_restore_job_event_count: 43,
    post_restore_inspection_fingerprint: `sha256:${"6".repeat(64)}`,
    status: "RESTORED_COPY_VERIFIED",
    restore_mode: "new_directory_only",
    archived_payloads: "VERIFIED_EXTERNAL_NOT_REHYDRATED",
    live_workspace_changed: false,
    automatic_execution: "NOT_PERFORMED",
    hardware_access: "NOT_PERFORMED",
    producer_authenticity: "NOT_VERIFIED",
    external_identity_and_artifact_files: "NOT_CHECKED",
    availability: "observed_during_rehearsal_only"
  };
}

function rehearsalReview(sourceHash, change = {}) {
  return {
    schema_version: "forgegate.recovery-rehearsal-review.v1",
    review_id: `sha256:${"7".repeat(64)}`,
    source_receipt_sha256: sourceHash,
    receipt: rehearsalReceipt(),
    disposition: "VERIFIED_RESTORED_COPY",
    path_input: "NOT_ACCEPTED",
    restore_execution: "NOT_PERFORMED_BY_REVIEW",
    live_workspace_switch: "NOT_PERFORMED",
    continuing_availability: "NOT_CHECKED",
    ...change
  };
}

function bytesFor(value) {
  const bytes = new TextEncoder().encode(typeof value === "string" ? value : JSON.stringify(value));
  return {bytes, hash: createHash("sha256").update(bytes).digest("hex")};
}

async function start(role = "operator") {
  const app = await harness();
  runInContext(`session={principal:{role:${JSON.stringify(role)},project_ids:['sample-api'],display_name:'Recovery reviewer'},csrf_token:'fixture-csrf'};window.location.hash='#/recovery';currentRoute='recovery';`, app.context);
  await runInContext("renderRecovery()", app.context);
  return app;
}

function all(root, tag) {
  return [...(root.tag === tag ? [root] : []), ...root.children.flatMap((child) => all(child, tag))];
}

function named(app, label) {
  return all(app.root, "button").find((item) => item.text === label);
}

async function click(app, label) {
  const control = named(app, label);
  assert.ok(control, label);
  await control.listeners.click[0]();
  await flush();
}

function select(app, value) {
  const {bytes, hash} = bytesFor(value);
  app.root.querySelector("input").files = [{name: "readiness.json", size: bytes.byteLength, arrayBuffer: async () => bytes.buffer}];
  return {bytes, hash};
}

function selectRehearsal(app, value) {
  const {bytes, hash} = bytesFor(value);
  const input = all(app.root, "input")[1];
  input.files = [{name: "REHEARSAL.json", size: bytes.byteLength, arrayBuffer: async () => bytes.buffer}];
  return {bytes, hash, input};
}

for (const status of ["READY", "INCOMPLETE"]) {
  test(`validated ${status} report preserves recovery boundaries`, async () => {
    const app = await start();
    const {hash} = select(app, report(status));
    app.responses.push({status: 200, body: handoff(hash, status)});
    await click(app, "Review recovery report");
    const request = app.requests.at(-1);
    assert.equal(request.path, "/app/api/recovery-review");
    assert.equal(request.options.headers.get("X-ForgeGate-CSRF"), "fixture-csrf");
    assert.equal(JSON.parse(request.options.body).expected_sha256, hash);
    assert.match(app.root.text, status === "READY" ? /Ready for an explicit rehearsal/ : /Recovery is blocked/);
    assert.match(app.root.text, /Live availability NOT_CHECKED/);
    assert.match(app.root.text, /past offline observation/);
    assert.match(app.root.text, /Downloading this JSON performs no restore/);
    assert.notEqual(named(app, "Download reviewed handoff JSON"), undefined);
  });
}

test("selecting another report after success enables a fresh explicit review", async () => {
  const app = await start();
  const first = select(app, report("READY"));
  app.responses.push({status: 200, body: handoff(first.hash, "READY")});
  await click(app, "Review recovery report");
  assert.equal(named(app, "Review recovery report").disabled, true);

  const second = select(app, report("INCOMPLETE"));
  for (const listener of app.root.querySelector("input").listeners.change ?? []) listener();
  assert.equal(named(app, "Review recovery report").disabled, false);
  app.responses.push({status: 200, body: handoff(second.hash, "INCOMPLETE")});
  await click(app, "Review recovery report");
  assert.match(app.root.text, /Recovery is blocked/);
});

test("invalid schema and oversized report stay in the browser", async () => {
  const app = await start();
  select(app, {schema_version: "unknown"});
  await click(app, "Review recovery report");
  assert.equal(app.requests.length, 1);
  assert.match(app.root.text, /DASHBOARD_RECOVERY_IMPORT_INVALID/);

  const input = app.root.querySelector("input");
  input.files = [{name: "large.json", size: 262145, arrayBuffer: async () => new ArrayBuffer(0)}];
  await click(app, "Review recovery report");
  assert.equal(app.requests.length, 1);
  assert.match(app.root.text, /DASHBOARD_RECOVERY_IMPORT_TOO_LARGE/);
});

for (const status of [409, 429, 500]) {
  test(`recovery review ${status} is visible and never automatically retried`, async () => {
    const app = await start();
    select(app, report());
    app.responses.push({status});
    await click(app, "Review recovery report");
    assert.equal(app.requests.length, 2);
    assert.match(app.root.text, /FIXTURE_ERROR/);
    await flush();
    assert.equal(app.requests.length, 2);
  });
}

test("producer cannot import a recovery report", async () => {
  const app = await start("producer");
  assert.equal(app.requests.length, 1);
  assert.equal(app.root.querySelector("input"), null);
  assert.match(app.root.text, /Operator session required/);
});

test("late recovery response cannot replace a different route", async () => {
  const app = await start();
  const {hash} = select(app, report());
  let finish;
  app.responses.push(() => new Promise((resolve) => { finish = resolve; }));
  const pending = named(app, "Review recovery report").listeners.click[0]();
  for (let attempt = 0; attempt < 10 && finish === undefined; attempt += 1) await flush();
  assert.equal(typeof finish, "function");
  runInContext("renderActivation()", app.context);
  finish({status: 200, body: handoff(hash)});
  await pending;
  await flush();
  assert.match(app.root.text, /Start local activation/);
  assert.doesNotMatch(app.root.text, /Ready for an explicit rehearsal/);
});

test("completed rehearsal receipt renders exact restored-copy identities and limits", async () => {
  const app = await start();
  const {hash} = selectRehearsal(app, rehearsalReceipt());
  app.responses.push({status: 200, body: rehearsalReview(hash)});
  await click(app, "Review rehearsal receipt");
  const request = app.requests.at(-1);
  assert.equal(request.path, "/app/api/recovery-rehearsal-review");
  assert.equal(request.options.headers.get("X-ForgeGate-CSRF"), "fixture-csrf");
  assert.equal(JSON.parse(request.options.body).expected_sha256, hash);
  assert.match(app.root.text, /Restored copy verified/);
  assert.match(app.root.text, /Restored tasks 27/);
  assert.match(app.root.text, /Task events 43/);
  assert.match(app.root.text, /VERIFIED_EXTERNAL_NOT_REHYDRATED/);
  assert.match(app.root.text, /did not read a server path/);
  assert.match(app.root.text, /check continuing availability/);
  assert.match(app.root.text, /control hardware/);
});

test("rehearsal receipt reselection clears old result and permits a new review", async () => {
  const app = await start();
  const first = selectRehearsal(app, rehearsalReceipt());
  app.responses.push({status: 200, body: rehearsalReview(first.hash)});
  await click(app, "Review rehearsal receipt");
  assert.equal(named(app, "Review rehearsal receipt").disabled, true);
  const secondValue = rehearsalReceipt();
  secondValue.completed_at = "2026-09-08T00:46:59Z";
  const second = selectRehearsal(app, secondValue);
  for (const listener of second.input.listeners.change ?? []) listener();
  assert.equal(named(app, "Review rehearsal receipt").disabled, false);
  assert.doesNotMatch(app.root.text, /Restored tasks 27/);
  app.responses.push({status: 200, body: rehearsalReview(second.hash)});
  await click(app, "Review rehearsal receipt");
  assert.match(app.root.text, /Restored copy verified/);
});

test("invalid and oversized rehearsal receipts are rejected in the browser", async () => {
  const app = await start();
  selectRehearsal(app, {schema_version: "unknown"});
  await click(app, "Review rehearsal receipt");
  assert.equal(app.requests.length, 1);
  assert.match(app.root.text, /DASHBOARD_REHEARSAL_IMPORT_INVALID/);
  const input = all(app.root, "input")[1];
  input.files = [{name: "large.json", size: 1048577, arrayBuffer: async () => new ArrayBuffer(0)}];
  await click(app, "Review rehearsal receipt");
  assert.equal(app.requests.length, 1);
  assert.match(app.root.text, /DASHBOARD_REHEARSAL_IMPORT_TOO_LARGE/);
});

for (const status of [409, 413, 429, 500]) {
  test(`rehearsal review ${status} is visible and never automatically retried`, async () => {
    const app = await start();
    selectRehearsal(app, rehearsalReceipt());
    app.responses.push({status});
    await click(app, "Review rehearsal receipt");
    assert.equal(app.requests.length, 2);
    assert.match(app.root.text, /FIXTURE_ERROR/);
    await flush();
    assert.equal(app.requests.length, 2);
  });
}

test("inconsistent rehearsal service response is rejected", async () => {
  const app = await start();
  const {hash} = selectRehearsal(app, rehearsalReceipt());
  app.responses.push({status: 200, body: rehearsalReview(hash, {continuing_availability: "CHECKED"})});
  await click(app, "Review rehearsal receipt");
  assert.match(app.root.text, /DASHBOARD_REHEARSAL_RESPONSE_INVALID/);
  assert.doesNotMatch(app.root.text, /Restored tasks 27/);
});

test("late rehearsal review cannot replace a different route", async () => {
  const app = await start();
  const {hash} = selectRehearsal(app, rehearsalReceipt());
  let finish;
  app.responses.push(() => new Promise((resolve) => { finish = resolve; }));
  const pending = named(app, "Review rehearsal receipt").listeners.click[0]();
  for (let attempt = 0; attempt < 10 && finish === undefined; attempt += 1) await flush();
  runInContext("renderActivation()", app.context);
  finish({status: 200, body: rehearsalReview(hash)});
  await pending;
  await flush();
  assert.match(app.root.text, /Start local activation/);
  assert.doesNotMatch(app.root.text, /Restored copy verified/);
});
