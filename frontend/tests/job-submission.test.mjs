import assert from 'node:assert/strict';
import {test} from 'node:test';
import {runInContext} from 'node:vm';
import {createHash} from 'node:crypto';
import {harness, flush} from './harness.mjs';

const text='<testsuite tests="4" failures="1"/>';
const bytes=new TextEncoder().encode(text), hash=createHash('sha256').update(bytes).digest('hex');
const candidate={candidate_id:`cand-${'b'.repeat(24)}`,project_id:'sample-api',commit_sha:'a'.repeat(40),revision:1,status:'COLLECTING'};
const job={job_id:`job-${'a'.repeat(32)}`,candidate_id:candidate.candidate_id,project_id:'sample-api',revision:0,state:'QUEUED',request_fingerprint:'sha256:fixture',authority:'AUTHENTICATED_DASHBOARD'};
const all=(n,tag)=>[...(n.tag===tag?[n]:[]),...n.children.flatMap(c=>all(c,tag))];
const find=(a,label)=>all(a.root,'button').find(b=>b.text===label);
async function click(a,label){const b=find(a,label); assert.ok(b,label); await b.listeners.click[0](); await flush();}
async function start(){
  const a=await harness(); a.context.candidateFixture=candidate; a.context.jobFixture=job;
  runInContext("session={csrf_token:'fixture-csrf',principal:{role:'operator',project_ids:['sample-api'],display_name:'Synthetic operator'}};window.location.hash='#/evidence';openJUnitImport(document.querySelector('#app'),candidateFixture,undefined,false,true);",a.context);
  const inputs=all(a.root,'input'); a.root.querySelector('form').reportValidity=()=>true;
  inputs[0].files=[{name:'synthetic.xml',size:bytes.length,arrayBuffer:async()=>bytes.buffer}];
  inputs[2].value='synthetic';inputs[3].value='1';inputs[4].value='2026-01-01T00:00:00Z';
  return {...a,inputs};
}
function preview(warnings=[],rejected=false){return {status:200,body:{schema_version:'forgegate.dashboard-collection-preview.v1',candidate_id:candidate.candidate_id,expected_revision:1,assembly:warnings.length||rejected?null:{assembly_id:'sha256:fixture'},assembly_json:'{"assembly_id":"sha256:fixture"}',collections:[{status:rejected?'REJECTED':'COMPLETE',artifacts:[{sha256:hash,size_bytes:bytes.length}],evidence:[{value:{total:4,failures:1}}],warnings,rejected_records:rejected?[{code:'REJECTED',message:'bad input'}]:[]}]}};}
async function review(a){a.responses.push(preview());await click(a,'Preview report — no binding');await click(a,'Review durable submission');}

test('durable review freezes exact bytes and uses a separate idempotent submission, never run/bind',async()=>{
  const a=await start();await review(a);
  assert.equal(a.requests.length,2);assert.match(a.root.text,/retains the exact report bytes/);assert.match(a.root.text,new RegExp(hash));
  assert.equal(find(a,'Confirm evidence binding'),undefined);
  let finish;a.responses.push(()=>new Promise(resolve=>{finish=resolve;}));
  const confirm=find(a,'Confirm task submission');confirm.click();confirm.click();await flush();
  assert.equal(a.requests.length,3);const req=a.requests.at(-1),body=JSON.parse(req.options.body);
  assert.equal(req.path,'/app/api/jobs?project_id=sample-api');assert.ok(req.options.headers.get('Idempotency-Key'));assert.equal(req.options.headers.get('X-ForgeGate-CSRF'),'fixture-csrf');
  assert.equal(body.collection.expected_revision,1);assert.equal(Buffer.from(body.collection.reports[0].content_base64,'base64').toString(),text);assert.equal(body.collection.retain_warnings,false);
  finish({status:200,body:job});await flush();assert.match(a.root.text,/Retained QUEUED/);assert.match(a.root.text,/No execution was started/);assert.equal(a.requests.length,3);
  assert.ok(all(a.root,'a').some(link=>link.href.includes(job.job_id)));
});
test('closing reviewed submission does not enqueue',async()=>{const a=await start();await review(a);await click(a,'Back without submission');assert.equal(a.requests.length,2);});
test('durable warning consent preserves reports and explicitly records consent',async()=>{
  const a=await start();a.responses.push(preview([{code:'WARN',message:'review me'}]));await click(a,'Preview report — no binding');assert.equal(find(a,'Review durable submission'),undefined);
  const accepted=preview();accepted.body.collections[0].warnings=[{code:'WARN',message:'review me'}];a.responses.push(accepted);await click(a,'Retain these warnings and preview again');await click(a,'Review durable submission');
  a.responses.push({status:200,body:job});await click(a,'Confirm task submission');assert.equal(JSON.parse(a.requests.at(-1).options.body).collection.retain_warnings,true);
});
test('rejected preview cannot enqueue',async()=>{const a=await start();a.responses.push(preview([],true));await click(a,'Preview report — no binding');assert.equal(find(a,'Review durable submission'),undefined);assert.equal(a.requests.length,2);});
for(const status of [409,413,429,500,503])test(`submission HTTP ${status} does not retry or execute`,async()=>{
  const a=await start();await review(a);a.responses.push({status,body:{error:{code:'FIXTURE_SUBMIT_ERROR',message:'failure',request_id:'test-request'}}});await click(a,'Confirm task submission');await flush();
  assert.equal(a.requests.length,3);assert.match(a.root.text,/FIXTURE_SUBMIT_ERROR/);assert.ok(find(a,'Close and inspect Jobs'));assert.equal(find(a,'Confirm task submission'),undefined);
});
test('late submission response after session change cannot reveal a task link',async()=>{
  const a=await start();await review(a);let finish;a.responses.push(()=>new Promise(resolve=>{finish=resolve;}));find(a,'Confirm task submission').click();await flush();runInContext('session=null;renderActivation()',a.context);finish({status:200,body:job});await flush();assert.doesNotMatch(a.root.text,/Inspect submitted task/);
});
test('foreground execution is separately confirmed once, with revision and CSRF',async()=>{
  const a=await start();a.root.replaceChildren();
  runInContext("reviewJobAction(document.querySelector('#app'),jobFixture,'run',document.querySelector('#app'))",a.context);
  assert.match(a.root.text,/does not stop parsing/);assert.match(a.root.text,/Retained request fingerprint/);assert.equal(a.requests.length,1);
  a.responses.push({status:200,body:{...job,state:'SUCCEEDED',revision:4,execution_owner_id:`executor-${'b'.repeat(32)}`,lease_renewal_count:2}});const b=find(a,'Confirm execution');b.click();b.click();await flush();
  assert.equal(a.requests.length,2);assert.match(a.requests.at(-1).path,/\/run\?project_id=sample-api$/);assert.deepEqual(JSON.parse(a.requests.at(-1).options.body),{expected_revision:0});assert.equal(a.requests.at(-1).options.headers.get('X-ForgeGate-CSRF'),'fixture-csrf');assert.match(a.root.text,/not a policy PASS/);
});
for(const state of ['FAILED','CANCELLED','INTERRUPTED'])test(`execution returns retained ${state} without claiming success`,async()=>{
  const a=await start();a.root.replaceChildren();runInContext("reviewJobAction(document.querySelector('#app'),jobFixture,'run',document.querySelector('#app'))",a.context);
  a.responses.push({status:200,body:{...job,state,revision:4,execution_owner_id:`executor-${'b'.repeat(32)}`,lease_renewal_count:2}});await click(a,'Confirm execution');assert.match(a.root.text,new RegExp(`Observed ${state}`));assert.doesNotMatch(a.root.text,/Recorded SUCCEEDED/);
});
