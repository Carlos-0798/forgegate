import assert from "node:assert/strict";
import { test } from "node:test";
import { runInContext } from "node:vm";
import { createHash } from "node:crypto";
import { harness, flush } from "./harness.mjs";

const bytes = new TextEncoder().encode('<testsuite tests="4" failures="1" skipped="1"/>');
const hash = createHash("sha256").update(bytes).digest("hex");
const candidate = { candidate_id: `cand-${"a".repeat(24)}`, commit_sha: "b".repeat(40), revision: 1, status: "COLLECTING" };
const assembly = {schema_version: "forgegate.evidence-bundle-assembly.v1", assembly_id: "sha256:fixture", bundle: {candidate_commit: candidate.commit_sha, evidence: [{}]}, collections: [{}], warning_disposition: "none"};
function preview(options = {}) {
  return {status: 200, body: {
    schema_version: "forgegate.dashboard-junit-preview.v1", candidate_id: candidate.candidate_id,
    expected_revision: 1, assembly, assembly_json: JSON.stringify(assembly),
    collection: {status: "COMPLETE", artifacts: [{sha256: hash, size_bytes: bytes.length}],
      evidence: [{value: {total: 4, passed: 2, failures: 1, skipped: 1}}], warnings: [], rejected_records: []},
    ...options
  }};
}
const all = (node, tag) => [...(node.tag === tag ? [node] : []), ...node.children.flatMap((child) => all(child, tag))];
const findButton = (node, text) => all(node, "button").find((button) => button.textContent === text);
async function app() {
  const a = await harness();
  a.context.fixture = candidate;
  runInContext("session = {csrf_token:'fixture',principal:{role:'operator'}}; openJUnitImport(document.querySelector('#app'), fixture);", a.context);
  const dialog = a.root.querySelector("dialog");
  const form = dialog.querySelector("form");
  form.reportValidity = () => true;
  const inputs = all(form, "input");
  inputs[0].files = [{name: "fixture.xml", size: bytes.length, arrayBuffer: async () => bytes.buffer}];
  inputs[2].value = "fixture-tool";
  inputs[3].value = "1";
  inputs[4].value = "2026-01-01T00:00:00Z";
  return {...a, dialog, form, inputs};
}
async function click(a, text) {
  const b = findButton(a.dialog, text);
  assert.ok(b, text);
  await b.listeners.click[0]();
  await flush();
}

test("raw preview preserves bytes and requires separate binding confirmation", async () => {
  const a = await app();
  a.responses.push(preview());
  await click(a, "Preview report — no binding");
  assert.match(a.dialog.text, /"passed": 2/);
  assert.match(a.dialog.text, /not a release decision/);
  assert.equal(a.requests.length, 2);
  const body = JSON.parse(a.requests.at(-1).options.body);
  assert.equal(Buffer.from(body.content_base64, "base64").toString(), new TextDecoder().decode(bytes));
  assert.equal(body.collected_at, "2026-01-01T00:00:00Z");
  assert.equal(body.retain_warnings, false);
  assert.equal(body.server_path, undefined);
  assert.equal(body.filename, undefined);
  await click(a, "Review immutable binding");
  assert.equal(a.requests.length, 2);
  assert.match(a.dialog.text, /Confirm evidence binding/);
  assert.match(a.dialog.text, /Original report SHA-256/);
  a.responses.push({status: 200, body: {binding_id:"fixture"}});
  await click(a, "Confirm evidence binding");
  assert.match(a.requests.at(-1).path, /\/evidence$/);
  assert.equal(JSON.parse(a.requests.at(-1).options.body).assembly.assembly_id, "sha256:fixture");
});

test("warnings block binding until explicit retained-warning preview", async () => {
  const a = await app();
  const warning = preview({assembly: null});
  warning.body.collection.warnings = [{code:"COUNT_MISMATCH", message:"Declared count differs"}];
  a.responses.push(warning);
  await click(a, "Preview report — no binding");
  assert.equal(findButton(a.dialog, "Review immutable binding"), undefined);
  assert.match(a.dialog.text, /COUNT_MISMATCH/);
  a.responses.push(preview());
  await click(a, "Retain these warnings and preview again");
  assert.equal(JSON.parse(a.requests.at(-1).options.body).retain_warnings, true);
  assert.ok(findButton(a.dialog, "Review immutable binding"));
});

test("rejected report and hostile issue text cannot become a binding", async () => {
  const a = await app();
  const rejected = preview({assembly:null});
  rejected.body.collection.status = "REJECTED";
  rejected.body.collection.evidence = [];
  rejected.body.collection.rejected_records = [{code:"BAD_XML", message:"<img src=x onerror=alert(1)>"}];
  a.responses.push(rejected);
  await click(a, "Preview report — no binding");
  assert.equal(findButton(a.dialog, "Review immutable binding"), undefined);
  assert.equal(a.dialog.querySelector("img"), null);
  assert.match(a.dialog.text, /BAD_XML/);
});

for (const invalid of ["size", "empty", "commit", "time", "future"]) {
  test(`invalid local ${invalid} sends no report`, async () => {
    const a = await app();
    if (invalid === "size") a.inputs[0].files[0].size = 1048577;
    if (invalid === "empty") a.inputs[0].files[0].size = 0;
    if (invalid === "commit") a.inputs[1].value = "c".repeat(40);
    if (invalid === "time") a.inputs[4].value = "2026-01-01";
    if (invalid === "future") a.inputs[4].value = "2999-01-01T00:00:00Z";
    await click(a, "Preview report — no binding");
    assert.equal(a.requests.length, 1);
    assert.equal(findButton(a.dialog, "Review immutable binding"), undefined);
    assert.match(a.dialog.text, /Browser validation — not an HTTP response/);
    assert.match(a.dialog.text, /DASHBOARD_JUNIT_INVALID/);
  });
}

for (const action of ["close", "logout", "navigate"]) {
  test(`late preview after ${action} is discarded`, async () => {
    const a = await app();
    let finish;
    a.responses.push(() => new Promise((resolve) => {finish = resolve;}));
    const pending = click(a, "Preview report — no binding");
    while (!finish) await flush();
    if (action === "close") a.dialog.close();
    if (action === "logout") runInContext("session = null", a.context);
    if (action === "navigate") runInContext("window.location.hash = '#/overview'", a.context);
    finish(preview());
    await pending;
    assert.equal(findButton(a.dialog, "Review immutable binding"), undefined);
  });
}

for (const code of [401, 409, 413, 422, 429, 500]) {
  test(`preview HTTP ${code} does not retry or write`, async () => {
    const a = await app();
    a.responses.push({status:code});
    await click(a, "Preview report — no binding");
    assert.equal(a.requests.length, 2);
    assert.equal(findButton(a.dialog, "Review immutable binding"), undefined);
  });
}

test("mismatched response hash blocks binding", async () => {
  const a = await app();
  const wrong = preview();
  wrong.body.collection.artifacts[0].sha256 = "wrong";
  a.responses.push(wrong);
  await click(a, "Preview report — no binding");
  assert.match(a.dialog.text, /hash or size mismatch/);
  assert.equal(findButton(a.dialog, "Review immutable binding"), undefined);
});
