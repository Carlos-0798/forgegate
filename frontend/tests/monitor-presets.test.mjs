import assert from "node:assert/strict";
import { test } from "node:test";
import { runInContext } from "node:vm";
import { harness, flush } from "./harness.mjs";

const ok = body => ({status: 200, body});
const principal = {role: "operator", display_name: "Monitor operator", project_ids: ["sample-api"], identity_id: "identity", trust_store_id: "trust", expires_at: "2099-01-01T00:00:00Z"};
const presets = [
  {preset_id: "demo", name: "Demo cycle", adapter: "forgegate.simulated-demo.v1", port: null, stale_after_seconds: 3},
  {preset_id: "board", name: "Saved board", adapter: "msp430.uart.v1", port: "COM4", stale_after_seconds: 3}
];
const view = (state = "STOPPED", revision = 0, extra = {}) => ({
  schema_version: "forgegate.monitor-control.v1", project_id: "sample-api", presets,
  session: {state, revision, run_id: state === "STOPPED" ? null : "run-1", active_preset_id: state === "STOPPED" ? null : "demo", detail_code: `MONITOR_${state}`, detail_message: `Monitor is ${state.toLowerCase()}.`, ...extra}
});
const source = (extra = {}) => ({source_id: "source", source_type: "msp430.uart.v1", display_name: "Saved source", access_mode: "READ_ONLY", connection: "CONNECTED", heartbeat: "NORMAL", device_health: "FAULT", detail_code: "FIXTURE_STATUS", detail_message: "Reported fixture status.", endpoint: "COM4", protocol: "uart.v1", baud_rate: 115200, expected_interval_seconds: 1, stale_after_seconds: 3, observed_at: "2026-09-09T12:00:00Z", last_heartbeat_at: "2026-09-09T12:00:00Z", heartbeat_age_seconds: 0.1, sequence: 8, uptime_ms: 8000, device_state: "FAULT", fault_flags: "0015", reported_issues: [{code: "fixture", label: "Fixture issue", mask: "0015"}], frames_received: 8, protocol_errors: 0, sequence_gaps: 0, reconnects: 0, evidence_boundary: "LIVE_STATUS_ONLY_NOT_RELEASE_EVIDENCE", hardware_control: "NOT_PERFORMED", ...extra});
const status = (sources = []) => ok({schema_version: "forgegate.live-status.v1", observed_at: "2026-09-09T12:00:00Z", refresh_after_seconds: 1, sources});
const nodes = node => [node, ...node.children.flatMap(nodes)];
const find = (app, tag, text) => nodes(app.root).find(node => node.tag === tag && node.textContent === text);
const start = app => find(app, "button", "Start monitoring");
const stop = app => find(app, "button", "Stop monitoring") ?? find(app, "button", "Retry stop monitoring");
const reload = app => find(app, "button", "Reload monitor session");
const writes = app => app.requests.filter(request => request.options.method === "POST");
async function setup(role = "operator") {
  const app = await harness();
  runInContext(`session = {principal: ${JSON.stringify({...principal, role})}, csrf_token: 'test-csrf'}; window.location.hash = '#/devices'; currentRoute = 'devices';`, app.context);
  return app;
}
async function opened(control = view(), sources = [], role = "operator") {
  const app = await setup(role);
  app.responses.push(status(sources), ok(control));
  await runInContext("renderDevices()", app.context);
  return app;
}
async function refresh(app, control, sources = []) {
  app.responses.push(status(sources), ok(control));
  find(app, "button", "Refresh now").click();
  await flush();
}

test("saved presets offer exact choices and explicit simulated boundaries without starting a monitor", async () => {
  const app = await opened();
  assert.deepEqual(app.requests.slice(-2).map(request => request.path), ["/app/api/live-status", "/app/api/monitor-presets"]);
  assert.equal(app.root.querySelector("select").value, "demo");
  assert.match(app.root.text, /SIMULATED DEMO.*NO HARDWARE OBSERVATION/);
  assert.match(app.root.text, /states change every 5 seconds and repeat every 30 seconds/);
  assert.match(app.root.text, /The Dashboard server stays running/);
  assert.match(app.root.text, /No monitor is currently running/);
  assert.doesNotMatch(app.root.text, /Restart the Dashboard/);
  assert.equal(start(app).disabled, false);
  assert.equal(stop(app).disabled, true);
  assert.equal(app.root.querySelector("input"), null);
  assert.equal(writes(app).length, 0);
});

test("null monitor catalog retains the legacy monitor hint and no preset controls", async () => {
  const app = await opened(null);
  assert.match(app.root.text, /Restart the Dashboard with --msp430-port COM4/);
  assert.equal(app.root.querySelector("select"), null);
  assert.equal(start(app), undefined);
});

test("read-only sessions show monitor state but expose no start or stop actions", async () => {
  const app = await opened(view("RUNNING", 1), [], "producer");
  assert.match(app.root.text, /Read-only session. An operator must start or stop/);
  assert.equal(start(app), undefined);
  assert.equal(stop(app), undefined);
  assert.equal(app.root.querySelector("select").disabled, true);
  assert.equal(writes(app).length, 0);
});

test("start captures saved preset and revision, applies CSRF, and blocks duplicate commands while pending", async () => {
  const app = await opened(view("STOPPED", 7));
  const selector = app.root.querySelector("select");
  selector.value = "board";
  selector.listeners.change[0]();
  assert.match(app.root.text, /COM4.*stale after 3 seconds/);
  assert.match(app.root.text, /Starting the monitor does not establish a connection/);
  let finish;
  app.responses.push(() => new Promise(resolve => {finish = resolve;}));
  start(app).click();
  start(app).click();
  await flush();
  assert.equal(start(app).disabled, true);
  assert.equal(stop(app).disabled, true);
  assert.equal(reload(app).disabled, true);
  assert.equal(selector.disabled, true);
  assert.equal(writes(app).length, 1);
  const request = writes(app)[0];
  assert.equal(request.path, "/app/api/monitor-session/start");
  assert.deepEqual(JSON.parse(request.options.body), {preset_id: "board", expected_revision: 7});
  assert.equal(request.options.headers.get("X-ForgeGate-CSRF"), "test-csrf");
  assert.equal(request.options.credentials, "same-origin");
  finish(ok(view("RUNNING", 8, {active_preset_id: "board"})));
  await flush();
  assert.match(app.root.text, /Monitoring RUNNING · revision 8/);
  assert.equal(stop(app).disabled, false);
  assert.equal(start(app).disabled, true);
});

test("stop targets the current run only and allows a new start after confirmed STOPPED", async () => {
  const app = await opened(view("RUNNING", 2));
  app.responses.push(ok(view("STOPPED", 3)));
  stop(app).click();
  await flush();
  const request = writes(app)[0];
  assert.equal(request.path, "/app/api/monitor-session/stop");
  assert.deepEqual(JSON.parse(request.options.body), {run_id: "run-1"});
  assert.equal(request.options.headers.get("X-ForgeGate-CSRF"), "test-csrf");
  assert.equal(start(app).disabled, false);
  assert.equal(stop(app).disabled, true);
  assert.ok(app.requests.every(request => !/shutdown|exit/.test(request.path)));
});

test("STOPPING retains run ownership and enables explicit retry of bounded stop", async () => {
  const app = await opened(view("RUNNING", 2));
  app.responses.push(ok(view("STOPPING", 3)));
  stop(app).click();
  await flush();
  assert.equal(start(app).disabled, true);
  assert.equal(stop(app).textContent, "Retry stop monitoring");
  assert.equal(stop(app).disabled, false);
  app.responses.push(ok(view("STOPPED", 4)));
  stop(app).click();
  await flush();
  assert.deepEqual(writes(app).map(request => JSON.parse(request.options.body)), [{run_id: "run-1"}, {run_id: "run-1"}]);
  assert.equal(start(app).disabled, false);
});

for (const runId of [null, "run-1"]) {
  test(`ERROR ${runId === null ? "without" : "with"} a run exposes the recoverable lifecycle action`, async () => {
    const app = await opened(view("ERROR", 4, {run_id: runId, detail_code: "MONITOR_START_FAILED", detail_message: "The monitor did not start."}));
    assert.match(app.root.text, /MONITOR_START_FAILED: The monitor did not start/);
    assert.equal(start(app).disabled, runId !== null);
    assert.equal(stop(app).disabled, runId === null);
    assert.doesNotMatch(app.root.text, /CONNECTED|connection established/);
  });
}

test("409 retains a recoverable explanation and reloads current state before another action", async () => {
  const app = await opened();
  app.responses.push({status: 409, body: {error: {code: "MONITOR_REVISION_CONFLICT", message: "Another tab changed this monitor.", request_id: "conflict-1"}}});
  start(app).click();
  await flush();
  assert.match(app.root.text, /Another tab changed this monitor/);
  assert.match(app.root.text, /Reload authoritative state.*not be retried automatically/);
  assert.equal(start(app).disabled, true);
  assert.equal(stop(app).disabled, true);
  app.responses.push(ok(view("RUNNING", 5, {run_id: "other-run", active_preset_id: "board"})));
  reload(app).click();
  await flush();
  assert.match(app.root.text, /Monitoring RUNNING · revision 5/);
  assert.doesNotMatch(app.root.text, /MONITOR_REVISION_CONFLICT/);
  assert.equal(stop(app).disabled, false);
  assert.equal(writes(app).length, 1);
});

for (const response of [{status: 500}, {status: 403}, new Error("connection lost")]) {
  test(`failed start (${response.status ?? "network"}) claims no success and requires state reconciliation`, async () => {
    const app = await opened();
    app.responses.push(response);
    start(app).click();
    await flush();
    assert.match(app.root.text, /The request did not complete/);
    assert.doesNotMatch(app.root.text, /Monitoring RUNNING|CONNECTED/);
    assert.equal(start(app).disabled, true);
    assert.equal(reload(app).disabled, false);
    assert.equal(writes(app).length, 1);
  });
}

test("per-second polling preserves selector/button nodes, selection and focus while reconciling revisions", async () => {
  const app = await opened();
  const selector = app.root.querySelector("select");
  const startButton = start(app);
  const options = [...selector.children];
  selector.value = "board";
  selector.listeners.change[0]();
  selector.focus();
  app.responses.push(status(), ok(view("STOPPED", 2)));
  await app.tick();
  assert.equal(app.root.querySelector("select"), selector);
  assert.equal(start(app), startButton);
  assert.deepEqual(selector.children, options);
  assert.equal(selector.value, "board");
  assert.equal(runInContext("document.activeElement", app.context), selector);
  startButton.focus();
  await refresh(app, view("RUNNING", 3, {active_preset_id: "board"}));
  assert.equal(runInContext("document.activeElement", app.context), startButton);
  assert.equal(start(app), startButton);
  assert.equal(start(app).disabled, true);
  assert.equal(stop(app).disabled, false);
});

test("a pending stale catalog response cannot overwrite a newer stop result", async () => {
  const app = await opened();
  let finish;
  app.responses.push(ok(view("RUNNING", 1)));
  start(app).click();
  await flush();
  app.responses.push(() => new Promise(resolve => {finish = resolve;}));
  reload(app).click();
  await flush();
  app.responses.push(ok(view("STOPPED", 2)));
  stop(app).click();
  await flush();
  finish(ok(view("RUNNING", 1)));
  await flush();
  assert.match(app.root.text, /Monitoring STOPPED · revision 2/);
  assert.equal(start(app).disabled, false);
});

test("manual refresh and polling do not issue overlapping source reads", async () => {
  const app = await opened();
  let finish;
  app.responses.push(() => new Promise(resolve => {finish = resolve;}), ok(view()));
  const refreshButton = find(app, "button", "Refresh now");
  refreshButton.click();
  refreshButton.click();
  await flush();
  assert.equal(refreshButton.disabled, true);
  assert.equal(app.requests.filter(request => request.path === "/app/api/live-status").length, 2);
  finish(status());
  await flush();
  assert.equal(refreshButton.disabled, false);
});

for (const operation of ["start", "stop", "reload"]) {
  for (const result of [ok(view("RUNNING", 99)), {status: 401}]) {
    test(`late ${operation} ${result.status} after navigation cannot touch the new route or session`, async () => {
      const app = await opened(operation === "stop" ? view("RUNNING", 1) : view());
      let finish;
      app.responses.push(() => new Promise(resolve => {finish = resolve;}));
      ({start: start(app), stop: stop(app), reload: reload(app)})[operation].click();
      await flush();
      runInContext("window.location.hash = '#/projects'; root.replaceChildren(el('p', undefined, 'New route'));", app.context);
      finish(result);
      await flush();
      assert.equal(app.root.text.trim(), "New route");
      assert.equal(runInContext("session !== null", app.context), true);
    });
  }
}

for (const response of [ok(view("RUNNING", 99)), {status: 401}]) {
  test(`late initial catalog ${response.status} after logout cannot restore the Devices page`, async () => {
    const app = await setup();
    let finish;
    app.responses.push(status(), () => new Promise(resolve => {finish = resolve;}));
    const pending = runInContext("renderDevices()", app.context);
    await flush();
    runInContext("renderActivation()", app.context);
    finish(response);
    await pending;
    assert.match(app.root.text, /Start local activation/);
    assert.doesNotMatch(app.root.text, /Live devices|Monitoring RUNNING/);
    assert.equal(app.timers.size, 0);
  });
}

test("late source error after navigation cannot end a still-valid session", async () => {
  const app = await setup();
  let finish;
  app.responses.push(() => new Promise(resolve => {finish = resolve;}), ok(view()));
  const pending = runInContext("renderDevices()", app.context);
  await flush();
  runInContext("window.location.hash = '#/projects'; root.replaceChildren(el('p', undefined, 'New route'));", app.context);
  finish({status: 401});
  await pending;
  assert.equal(app.root.text.trim(), "New route");
  assert.equal(runInContext("session !== null", app.context), true);
});

test("late start after session replacement cannot alter the new authenticated session", async () => {
  const app = await opened();
  let finish;
  app.responses.push(() => new Promise(resolve => {finish = resolve;}));
  start(app).click();
  await flush();
  runInContext("session = {...session, csrf_token: 'new-session-csrf'}; root.replaceChildren(el('p', undefined, 'New session'));", app.context);
  finish({status: 401});
  await flush();
  assert.equal(app.root.text.trim(), "New session");
  assert.equal(runInContext("session.csrf_token", app.context), "new-session-csrf");
});

test("a newer Devices render rejects responses from the previous route generation", async () => {
  const app = await setup();
  let finish;
  app.responses.push(status(), () => new Promise(resolve => {finish = resolve;}));
  const previous = runInContext("renderDevices()", app.context);
  await flush();
  app.responses.push(status(), ok(view("STOPPED", 8)));
  await runInContext("renderDevices()", app.context);
  finish(ok(view("RUNNING", 7)));
  await previous;
  assert.match(app.root.text, /Monitoring STOPPED · revision 8/);
  assert.doesNotMatch(app.root.text, /Monitoring RUNNING/);
  assert.equal(app.timers.size, 1);
});

test("current 401 clears protected monitor content even after an earlier catalog error", async () => {
  const app = await opened();
  app.responses.push({status: 500});
  reload(app).click();
  await flush();
  app.responses.push(status(), {status: 401});
  find(app, "button", "Refresh now").click();
  await flush();
  assert.match(app.root.text, /Start local activation/);
  assert.equal(start(app), undefined);
  assert.equal(app.timers.size, 0);
});

test("unknown catalog state does not fabricate a legacy restart instruction", async () => {
  const app = await setup();
  app.responses.push(status(), {status: 500});
  await runInContext("renderDevices()", app.context);
  assert.match(app.root.text, /Reload the monitor session to check/);
  assert.doesNotMatch(app.root.text, /--msp430-port/);
  assert.equal(start(app).disabled, true);
  assert.equal(reload(app).disabled, false);
});

test("simulated source presentation never describes physical input or firmware observation", async () => {
  const app = await opened(view("RUNNING", 1), [source({data_origin: "SIMULATED"})]);
  const panel = app.root.querySelector(".live-source-panel");
  assert.match(panel.text, /SIMULATED SOURCE.*NO HARDWARE OBSERVATION/);
  assert.match(panel.text, /SIMULATED · Saved source/);
  assert.match(panel.text, /No serial port is opened/);
  assert.match(panel.text, /states change every 5 seconds and repeat every 30 seconds/);
  assert.match(panel.text, /Baud Not applicable \(simulated\)/);
  assert.doesNotMatch(panel.text, /endpoint is open for input|The firmware reports|LATEST VALID TEL FRAME|Decoded firmware reports/);
});

test("legacy source without data_origin retains the physical telemetry descriptions", async () => {
  const app = await opened(null, [source()]);
  const panel = app.root.querySelector(".live-source-panel");
  assert.match(panel.text, /The configured serial endpoint is open for input/);
  assert.match(panel.text, /The firmware reports FAULT/);
  assert.doesNotMatch(panel.text, /SIMULATED/);
});

test("refresh reconciles a changed preset catalog without replacing the selector", async () => {
  const app = await opened();
  const selector = app.root.querySelector("select");
  const changed = {...view("STOPPED", 1), presets: [presets[1]]};
  await refresh(app, changed);
  assert.equal(app.root.querySelector("select"), selector);
  assert.equal(selector.value, "board");
  assert.equal(selector.children.length, 1);
  await refresh(app, {...changed, presets: []});
  assert.equal(start(app).disabled, true);
  assert.match(app.root.text, /No saved preset is available/);
});
