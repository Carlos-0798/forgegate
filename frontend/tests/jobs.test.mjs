import assert from "node:assert/strict";
import {test} from "node:test";
import {runInContext} from "node:vm";
import {harness, flush} from "./harness.mjs";

const job = {schema_version:"forgegate.collection-job.v2",job_id: `job-${"a".repeat(32)}`, candidate_id: `cand-${"b".repeat(24)}`, project_id: "sample-api", state: "QUEUED", revision: 0, created_at: "2026-09-01T00:00:00Z", updated_at: "2026-09-01T00:00:00Z", lease_expires_at: null, result_fingerprint: null, request_fingerprint: "sha256:fixture", error_code: null, source_bytes: "retained_pending", authority: "LOCAL_CLI_NOT_AUTHENTICATED",execution_owner_id:null,lease_renewal_count:0};
const review = {record: job, events:[{record: job, actor:null}], result:null};
const page = (changes = {}) => ({status:200, body:{enabled:true, project_id:"sample-api", jobs:[job], next_after_job_id: job.job_id, has_more:false, observed_at:job.updated_at, ...changes}});
async function start(hash = "#/jobs?project_id=sample-api", role="operator") {
  const app = await harness();
  runInContext(`session={principal:{role:${JSON.stringify(role)},project_ids:['sample-api'],display_name:'Test operator'},csrf_token:'fixture-csrf'};window.location.hash=${JSON.stringify(hash)};`,app.context);
  return app;
}
function all(root, tag) { return [...(root.tag===tag?[root]:[]),...root.children.flatMap(child=>all(child,tag))]; }
function named(app, label) { return all(app.root,"button").find(b=>b.text===label); }

test("archived task shows backup dependency and history without result mutation actions",async()=>{
  const app=await start(`#/jobs?project_id=sample-api&job_id=${job.job_id}`);
  app.responses.push({status:200,body:{...review,record:{...job,state:"SUCCEEDED"},archive:{archived_at:job.updated_at,plan_fingerprint:"sha256:reviewed",plan:{backup_sha256:"c".repeat(64),result_size_bytes:2048}}}});
  await runInContext("renderJobs()",app.context);
  assert.match(app.root.text,/Archived result — external backup required/);
  assert.match(app.root.text,/cccccccc/);
  assert.match(app.root.text,/Result bytes moved logically 2048/);
  assert.match(app.root.text,/State history and recorded actors/);
  assert.match(app.root.text,/No new collection or policy decision/);
  assert.doesNotMatch(app.root.text,/No retained collection result/);
  for(const label of ["Review assembly download","Review evidence binding from task","Review execution","Review cancellation"])
    assert.equal(named(app,label),undefined);
});

test("job list preserves scope/cursor and exposes no execution button", async()=>{
  const app=await start(`#/jobs?project_id=sample-api&after_job_id=${job.job_id}&candidate_id=${job.candidate_id}`);
  app.responses.push(page({has_more:true}));
  await runInContext("renderJobs()",app.context);
  assert.match(app.requests.at(-1).path, /after_job_id=job-/);
  assert.match(app.requests.at(-1).path, /candidate_id=cand-/);
  assert.match(app.root.text,/Next job page/);
  assert.match(app.root.text,/Completion is not a policy PASS/);
  assert.equal(named(app,"Run job"),undefined);
});
test("disabled store is not shown as empty success",async()=>{
  const app=await start(); app.responses.push(page({enabled:false,jobs:[]}));
  await runInContext("renderJobs()",app.context);
  assert.match(app.root.text,/Job store not enabled/);
  assert.doesNotMatch(app.root.text,/No matching jobs/);
});
test("empty jobs is an explicit non-success state",async()=>{
  const app=await start(); app.responses.push(page({jobs:[]}));
  await runInContext("renderJobs()",app.context);
  assert.match(app.root.text,/Empty results do not prove successful collection/);
});
for(const hash of ["#/jobs?project_id=other","#/jobs?job_id=bad","#/jobs?candidate_id=bad","#/jobs?after_job_id=bad"]){
  test(`invalid job selection sends no query: ${hash}`,async()=>{
    const app=await start(hash); await runInContext("renderJobs()",app.context);
    assert.equal(app.requests.length,1); assert.match(app.root.text,/Invalid job selection/);
  });
}
test("producer cannot query tasks",async()=>{
  const app=await start("#/jobs","producer"); await runInContext("renderJobs()",app.context);
  assert.equal(app.requests.length,1); assert.match(app.root.text,/Operator session required/);
});
test("detail renders retained failure counts as text not policy PASS",async()=>{
  const app=await start(`#/jobs?project_id=sample-api&job_id=${job.job_id}`);
  app.responses.push({status:200,body:{...review,record:{...job,state:"SUCCEEDED"},result:{assembly:null,collections:[{collector_name:"<img src=x>",status:"COMPLETE",evidence:[{kind:"test.summary",scope:"repository",trust:"unsigned_local",verification_level:"declared",value:{total:4,failures:1}}],warnings:[],rejected_records:[]}]}}});
  await runInContext("renderJobs()",app.context);
  assert.match(app.root.text,/"failures": 1/); assert.match(app.root.text,/Actor not recorded/);
  assert.equal(app.root.querySelector("img"),null);
  assert.equal(named(app,"Review cancellation"),undefined);
});
test("cancellation requires confirmation; double clicks send one frozen command",async()=>{
  const app=await start(`#/jobs?project_id=sample-api&job_id=${job.job_id}`);
  app.responses.push({status:200,body:review}); await runInContext("renderJobs()",app.context);
  named(app,"Review cancellation").click(); assert.equal(app.requests.length,2);
  named(app,"Back without changes").click(); assert.equal(app.requests.length,2);
  named(app,"Review cancellation").click();
  const dialogs=all(app.root,"dialog"); const dialog=dialogs.at(-1);
  const confirm=all(dialog,"button").find(b=>b.text==="Confirm cancellation");
  let finish; app.responses.push(()=>new Promise(resolve=>{finish=resolve;}));
  confirm.click(); confirm.click(); await flush();
  assert.equal(app.requests.length,3);
  const request=app.requests.at(-1);
  assert.equal(request.options.headers.get("X-ForgeGate-CSRF"),"fixture-csrf");
  assert.deepEqual(JSON.parse(request.options.body),{expected_revision:0});
  finish({status:200,body:{...job,state:"CANCELLED",revision:1}}); await flush();
  assert.match(dialog.text,/Recorded CANCELLED at revision 1/);
});
for(const status of [409,429,500,503]){
  test(`job mutation ${status} offers reload without automatic retry`,async()=>{
    const app=await start(`#/jobs?project_id=sample-api&job_id=${job.job_id}`);
    app.responses.push({status:200,body:review}); await runInContext("renderJobs()",app.context);
    named(app,"Review cancellation").click(); app.responses.push({status});
    named(app,"Confirm cancellation").click(); await flush();
    assert.equal(app.requests.length,3); assert.match(app.root.text,/Close and refresh jobs/);
    assert.match(app.root.text,/FIXTURE_ERROR/);
    await flush(); assert.equal(app.requests.length,3);
  });
}
test("running task recovery is distinct from retry",async()=>{
  const app=await start(`#/jobs?project_id=sample-api&job_id=${job.job_id}`);
  const running={...job,state:"RUNNING",revision:3,lease_expires_at:"2026-09-01T00:05:00Z",execution_owner_id:`executor-${"c".repeat(32)}`,lease_renewal_count:2};
  app.responses.push({status:200,body:{...review,record:running}});
  await runInContext("renderJobs()",app.context);
  assert.match(app.root.text,/executor-cccc/); assert.match(app.root.text,/Lease renewals 2/);
  named(app,"Review interruption recovery").click();
  app.responses.push({status:200,body:{...running,state:"INTERRUPTED",revision:4,lease_expires_at:null}});
  named(app,"Confirm recovery").click(); await flush();
  assert.match(app.requests.at(-1).path,/\/recover\?/);
  assert.match(app.root.text,/No retry or execution is started/);
});
test("late detail response cannot replace another route or activation",async()=>{
  const app=await start(); let finish;
  app.responses.push(()=>new Promise(resolve=>{finish=resolve;}));
  const pending=runInContext("renderJobs()",app.context); await flush();
  runInContext("renderActivation()",app.context); finish(page()); await pending;
  assert.doesNotMatch(app.root.text,/Inspect job-/);
  assert.match(app.root.text,/Start local activation/);
});
test("expired session clears protected task data",async()=>{
  const app=await start(); app.responses.push({status:401});
  await runInContext("renderJobs()",app.context); assert.match(app.root.text,/Start local activation/);
});
