import assert from "node:assert/strict";
import { test } from "node:test";
import { runInContext } from "node:vm";
import { harness, flush } from "./harness.mjs";

const principal = {role: "operator", display_name: "Local reviewer", project_ids: ["sample-api", "second-project"], identity_id: "identity", trust_store_id: "trust", expires_at: "2099-01-01T00:00:00Z"};
const project = (id = "sample-api") => ({project_id: id, profile_version: 1, config_fingerprint: "sha256:profile", registered_at: "2026-09-09T12:00:00Z", config: {project: {id, name: `Project ${id}`, repository: "local", default_branch: "develop"}, release_tracks: {release: {policy: "release.yaml"}}}});
const candidate = (status, letter = "a", extra = {}) => ({candidate_id: `cand-${letter.repeat(24)}`, project_id: "sample-api", version: `version-${status}`, commit_sha: letter.repeat(40), source_branch: "develop", release_track: "release", status, revision: 1, created_at: "2026-09-09T12:00:00Z", updated_at: "2026-09-09T12:00:00Z", evaluation_id: status === "DRAFT" ? null : "evaluation", ...extra});
const ok = body => ({status: 200, body});
const overview = () => ok({principal, forgegate_version: "0.1.0a1", api_version: "v1", database_schema_version: 9, deployment: "loopback", hardware_access: "NOT_PERFORMED", limitations: ["Integrity does not authenticate the producer."]});
const projectPage = (list = [project()]) => ok({projects: list, has_more: false, next_after_project_id: null});
const candidatePage = (list = [], more = false) => ok({candidates: list, has_more: more, next_after_candidate_id: more ? list.at(-1).candidate_id : null});
const nodes = node => [node, ...node.children.flatMap(nodes)];
const find = (app, tag, text) => nodes(app.root).find(node => node.tag === tag && node.textContent === text);
async function appFor(route = "overview", role = "operator") {
  const app = await harness();
  runInContext(`session = {principal: ${JSON.stringify({...principal, role})}, csrf_token: 'test-csrf'}; window.location.hash = '#/${route}'; currentRoute = '${route}';`, app.context);
  return app;
}

test("workbench counts the loaded project page and directs outcomes to useful reviews", async () => {
  const app = await appFor();
  const items = [candidate("PASS"), candidate("FAIL", "b"), candidate("DRAFT", "c"), candidate("REVIEW", "d")];
  app.responses.push(overview(), projectPage(), candidatePage(items, true));
  await runInContext("renderOverview()", app.context);
  assert.equal(app.requests.at(-1).path, "/app/api/projects/sample-api/candidates?limit=25");
  assert.match(app.root.text, /4 candidates loaded for sample-api; more are available/);
  assert.match(app.root.text, /not project-wide totals or recency rankings/);
  const cards = nodes(app.root).filter(node => node.className === "metric-card");
  assert.deepEqual(cards.map(card => card.text.replace(/\s+/g, " ").trim()), ["Loaded candidates 4", "Needs investigation 2", "In progress 1", "Policy passed 1"]);
  assert.equal(find(app, "a", "Review handoff").href, `#/assurance?candidate_id=${items[0].candidate_id}`);
  assert.equal(find(app, "a", "Investigate decision").href, `#/decision?candidate_id=${items[1].candidate_id}`);
  assert.equal(find(app, "a", "Continue review").href, `#/evidence?candidate_id=${items[2].candidate_id}`);
  assert.match(app.root.text, /Integrity does not authenticate the producer/);
  assert.equal(app.root.querySelector("details").open, false);
  assert.doesNotMatch(app.root.text, /Planned|LATER GATES/);
  assert.match(app.root.text, /WORKSPACE.*REVIEW.*OPERATIONS/s);
});

test("Quick assessment opens the reviewed draft with selected project defaults and no write", async () => {
  const app = await appFor();
  app.responses.push(overview(), projectPage(), candidatePage());
  await runInContext("renderOverview()", app.context);
  find(app, "button", "Quick assessment").click();
  const dialog = app.root.querySelector("dialog");
  assert.equal(dialog.open, true);
  assert.match(dialog.text, /Project: Project sample-api · sample-api/);
  assert.equal(nodes(dialog).find(node => node.name === "branch").value, "develop");
  assert.equal(nodes(dialog).find(node => node.name === "track").value, "release");
  assert.equal(app.requests.length, 4);
  assert.ok(app.requests.every(request => !request.options?.method));
});

test("read-only workbench offers review but no candidate creation", async () => {
  const app = await appFor("overview", "producer");
  app.responses.push(overview(), projectPage(), candidatePage());
  await runInContext("renderOverview()", app.context);
  assert.equal(find(app, "button", "Quick assessment"), undefined);
  assert.match(app.root.text, /Read-only session/);
  assert.equal(find(app, "a", "Browse candidates").href, "#/candidates");
});

test("empty authorized project list does not fabricate a count or request candidates", async () => {
  const app = await appFor();
  app.responses.push(overview(), projectPage([]));
  await runInContext("renderOverview()", app.context);
  assert.match(app.root.text, /No registered projects in this session/);
  assert.equal(app.requests.length, 3);
  assert.equal(find(app, "button", "Quick assessment"), undefined);
});

test("project changes isolate pending workbench results", async () => {
  const app = await appFor();
  let finish;
  app.responses.push(overview(), projectPage([project(), project("second-project")]), () => new Promise(resolve => {finish = resolve;}));
  const pending = runInContext("renderOverview()", app.context);
  await flush();
  const selector = app.root.querySelector("select");
  selector.value = "second-project";
  app.responses.push(overview(), candidatePage([candidate("PASS", "d", {project_id: "second-project", version: "second-only"})]));
  selector.listeners.change[0]();
  await flush();
  finish(candidatePage([candidate("FAIL", "e", {version: "stale-first-project"})]));
  await pending;
  assert.match(app.root.text, /second-only/);
  assert.doesNotMatch(app.root.text, /stale-first-project/);
  assert.equal(app.requests.at(-1).path, "/app/api/projects/second-project/candidates?limit=25");
});

for (const stage of ["service", "projects", "candidates"]) {
  test(`late workbench ${stage} response cannot restore authenticated content after logout`, async () => {
    const app = await appFor();
    let finish;
    if (stage !== "service") app.responses.push(overview());
    if (stage === "candidates") app.responses.push(projectPage());
    app.responses.push(() => new Promise(resolve => {finish = resolve;}));
    const pending = runInContext("renderOverview()", app.context);
    await flush();
    runInContext("renderActivation()", app.context);
    finish(stage === "service" ? overview() : stage === "projects" ? projectPage() : candidatePage([candidate("FAIL")]));
    await pending;
    assert.match(app.root.text, /Start local activation/);
    assert.doesNotMatch(app.root.text, /version-FAIL|Your release workbench/);
    assert.equal(runInContext("projects.length", app.context), 0);
  });
}

test("late workbench error after navigation does not clear the new route", async () => {
  const app = await appFor();
  let finish;
  app.responses.push(overview(), projectPage(), () => new Promise(resolve => {finish = resolve;}));
  const pending = runInContext("renderOverview()", app.context);
  await flush();
  runInContext("window.location.hash = '#/candidates'; root.replaceChildren(el('p', undefined, 'new-route-content'));", app.context);
  finish({status: 401});
  await pending;
  assert.match(app.root.text, /new-route-content/);
  assert.ok(runInContext("session !== null", app.context));
});

test("current workbench 401 clears protected content", async () => {
  const app = await appFor();
  app.responses.push(overview(), projectPage(), {status: 401});
  await runInContext("renderOverview()", app.context);
  assert.match(app.root.text, /Start local activation/);
  assert.equal(app.root.querySelector("details"), null);
});

for (const stage of ["service", "candidates"]) {
  test(`${stage} errors retain a working manual refresh without inventing empty results`, async () => {
    const app = await appFor();
    if (stage === "candidates") app.responses.push(overview(), projectPage());
    app.responses.push({status: 500});
    await runInContext("renderOverview()", app.context);
    assert.match(app.root.text, /FIXTURE_ERROR/);
    assert.doesNotMatch(app.root.text, /0 candidates loaded/);
    app.responses.push(overview(), projectPage(), candidatePage([candidate("PASS")]));
    find(app, "button", "Refresh workspace").click();
    await flush();
    assert.match(app.root.text, /version-PASS/);
  });
}

test("candidate search and state filters combine on the loaded page without a write", async () => {
  const app = await appFor("candidates");
  app.responses.push(projectPage(), candidatePage([candidate("PASS"), candidate("FAIL", "b", {source_branch: "feature-special"}), candidate("FAIL", "c")], true));
  await runInContext("renderCandidates()", app.context);
  const controls = app.root.querySelector(".candidate-filters");
  const search = controls.querySelector("input");
  const state = controls.querySelector("select");
  state.value = "FAIL";
  state.listeners.change[0]();
  assert.match(app.root.text, /2 of 3 loaded candidates match/);
  search.value = "FEATURE-special";
  search.listeners.input[0]();
  assert.match(app.root.text, /1 of 3 loaded candidates match/);
  assert.equal(nodes(app.root).filter(node => node.tag === "tbody")[0].children.length, 1);
  search.value = "absent-from-page";
  search.listeners.input[0]();
  assert.match(app.root.text, /No matches on this page/);
  assert.match(app.root.text, /No project-wide search was performed/);
  find(app, "button", "Clear filters").click();
  assert.match(app.root.text, /3 of 3 loaded candidates match/);
  assert.equal(app.requests.length, 3);
});

test("candidate list refresh keeps server errors recoverable", async () => {
  const app = await appFor("candidates");
  app.responses.push(projectPage(), {status: 500});
  await runInContext("renderCandidates()", app.context);
  app.responses.push(candidatePage([candidate("PASS")]));
  find(app, "button", "Refresh candidates").click();
  await flush();
  assert.match(app.root.text, /version-PASS/);
});

test("late candidate list response cannot replace a newer project selection", async () => {
  const app = await appFor("candidates");
  let finish;
  app.responses.push(projectPage([project(), project("second-project")]), () => new Promise(resolve => {finish = resolve;}));
  const pending = runInContext("renderCandidates()", app.context);
  await flush();
  app.responses.push(candidatePage([candidate("PASS", "d", {version: "current-second"})]));
  await runInContext("selectedProjectId = 'second-project'; renderCandidates()", app.context);
  finish(candidatePage([candidate("FAIL", "e", {version: "old-first"})]));
  await pending;
  assert.match(app.root.text, /current-second/);
  assert.doesNotMatch(app.root.text, /old-first/);
});

test("late candidate list response after logout cannot render a protected table", async () => {
  const app = await appFor("candidates");
  let finish;
  app.responses.push(projectPage(), () => new Promise(resolve => {finish = resolve;}));
  const pending = runInContext("renderCandidates()", app.context);
  await flush();
  runInContext("renderActivation()", app.context);
  finish(candidatePage([candidate("PASS")]));
  await pending;
  assert.match(app.root.text, /Start local activation/);
  assert.equal(app.root.querySelector("table"), null);
});
