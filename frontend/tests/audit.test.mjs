import assert from "node:assert/strict";
import { test } from "node:test";
import { runInContext } from "node:vm";
import { harness, flush } from "./harness.mjs";

async function auditApp(hash = "#/audit?project_id=sample-api", role = "operator") {
  const app = await harness();
  runInContext(`session = {principal: {role: '${role}', project_ids: ['sample-api','second-project']}}; window.location.hash = ${JSON.stringify(hash)};`, app.context);
  return app;
}
const event = {
  event_id: "sha256:abc", sequence: 26, event_type: "candidate.created",
  occurred_at: "2026-09-06T12:00:00Z", project_id: "sample-api",
  candidate_id: `cand-${"a".repeat(24)}`, subject_schema_version: "forgegate.release-candidate.v2",
  subject_id: "subject", subject_fingerprint: "sha256:def", actor: null
};
const page = (events = [event], has_more = false) => ({status: 200, body: {
  events, has_more, next_after_sequence: events.at(-1)?.sequence ?? null
}});

test("audit renders exact identities, missing actor boundary and next cursor", async () => {
  const app = await auditApp();
  app.responses.push(page([event], true));
  await runInContext("renderAudit()", app.context);
  assert.match(app.requests.at(-1).path, /project_id=sample-api&after_sequence=0&limit=25/);
  assert.match(app.root.text, /sha256:abc/);
  assert.match(app.root.text, /Not recorded — no authenticated identity is inferred/);
  assert.match(app.root.text, /More events available/);
  assert.equal(app.root.querySelector("details").querySelector("summary").tag, "summary");
  assert.match(runInContext("auditHash('sample-api', '', 26)", app.context), /after_sequence=26/);
});

test("audit candidate filter and cursor survive a fresh route render", async () => {
  const app = await auditApp(`#/audit?project_id=sample-api&candidate_id=${event.candidate_id}&after_sequence=25`);
  app.responses.push(page());
  await runInContext("renderAudit()", app.context);
  const url = new URL(app.requests.at(-1).path, "http://localhost");
  assert.equal(url.searchParams.get("candidate_id"), event.candidate_id);
  assert.equal(url.searchParams.get("after_sequence"), "25");
  assert.match(app.root.text, /End of matching history/);
});

for (const hash of ["#/audit?project_id=forbidden", "#/audit?candidate_id=bad", "#/audit?after_sequence=-1", "#/audit?after_sequence=9007199254740992"]) {
  test(`invalid audit selection makes no request: ${hash}`, async () => {
    const app = await auditApp(hash);
    await runInContext("renderAudit()", app.context);
    assert.equal(app.requests.length, 1);
    assert.match(app.root.text, /Invalid audit selection/);
  });
}

test("producer audit page performs no query", async () => {
  const app = await auditApp("#/audit", "producer");
  await runInContext("renderAudit()", app.context);
  assert.equal(app.requests.length, 1);
  assert.match(app.root.text, /Operator session required/);
});

test("empty history remains unknown rather than a success claim", async () => {
  const app = await auditApp();
  app.responses.push(page([]));
  await runInContext("renderAudit()", app.context);
  assert.match(app.root.text, /No matching audit events/);
  assert.match(app.root.text, /not proof that an operation succeeded or failed/);
});

test("actor display is text-only and no session identifier is rendered", async () => {
  const app = await auditApp();
  app.responses.push(page([{...event, actor: {display_name: "<img src=x onerror=alert(1)>", role: "operator", identity_id: "sha256:identity", session_id: "session-not-for-display"}}]));
  await runInContext("renderAudit()", app.context);
  assert.match(app.root.text, /<img src=x onerror=alert\(1\)>/);
  assert.equal(app.root.querySelector("img"), null);
  assert.doesNotMatch(app.root.text, /session-not-for-display/);
});

test("audit 401 clears protected UI", async () => {
  const app = await auditApp();
  app.responses.push({status: 401});
  await runInContext("renderAudit()", app.context);
  assert.match(app.root.text, /Start local activation/);
  assert.equal(app.root.querySelector("details"), null);
});

test("audit errors retain a manual refresh action", async () => {
  const app = await auditApp();
  app.responses.push({status: 500});
  await runInContext("renderAudit()", app.context);
  assert.match(app.root.text, /Refresh audit page/);
  assert.match(app.root.text, /FIXTURE_ERROR/);
});

test("late audit response cannot expose data after logout", async () => {
  const app = await auditApp();
  let finish;
  app.responses.push(() => new Promise(resolve => {finish = resolve;}));
  const pending = runInContext("renderAudit()", app.context);
  await flush();
  runInContext("renderActivation()", app.context);
  finish(page());
  await pending;
  assert.match(app.root.text, /Start local activation/);
  assert.doesNotMatch(app.root.text, /sha256:abc/);
});
