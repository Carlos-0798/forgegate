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
