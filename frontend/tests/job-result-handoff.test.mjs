import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {test} from 'node:test';
import {runInContext} from 'node:vm';
import {flush, harness} from './harness.mjs';

const fp=(char)=>`sha256:${char.repeat(64)}`;
const candidate={candidate_id:`cand-${'b'.repeat(24)}`,project_id:'sample-api',commit_sha:'a'.repeat(40),revision:1,status:'COLLECTING'};
const assembly={schema_version:'forgegate.evidence-bundle-assembly.v1',assembly_id:fp('c'),warning_disposition:'none',bundle:{candidate_commit:candidate.commit_sha,generated_at:'2026-09-06T20:00:00Z',producer:'forgegate-dashboard',evidence:[{evidence_id:fp('e'),kind:'test.summary',scope:'repository',value:{total:4,passed:3,failures:1},unit:null,status:'observed',source_tool:'synthetic',source_version:'1',artifact:{path_or_uri:'report.xml',media_type:'application/xml',sha256:'1'.repeat(64),size_bytes:10},collected_at:'2026-09-06T19:00:00Z',trust:'unsigned_local',verification_level:'declared'}]},collections:[{collector_name:'junit',collector_version:'1',warnings:[]}]};
const job={job_id:`job-${'a'.repeat(32)}`,candidate_id:candidate.candidate_id,project_id:'sample-api',revision:2,state:'SUCCEEDED',request_fingerprint:fp('1'),result_fingerprint:fp('2'),candidate_fingerprint:fp('3'),authority:'AUTHENTICATED_DASHBOARD',source_bytes:'released_logically',updated_at:'2026-09-06T20:00:00Z',created_at:'2026-09-06T19:00:00Z',lease_expires_at:null,error_code:null};
const review={record:job,events:[],result:{collections:[],assembly}};
const bytes=new TextEncoder().encode(JSON.stringify(assembly));
const assemblyFingerprint=`sha256:${createHash('sha256').update(bytes).digest('hex')}`;
const media='application/vnd.forgegate.evidence-bundle-assembly+json';
const all=(n,tag)=>[...(n.tag===tag?[n]:[]),...n.children.flatMap(c=>all(c,tag))];
const find=(a,label)=>all(a.root,'button').find(b=>b.text===label);
async function click(a,label){const b=find(a,label);assert.ok(b,label);await b.listeners.click[0]();await flush();}
async function setup(role='operator', value=review){
  const a=await harness();
  a.context.reviewFixture=value;
  runInContext(`session={csrf_token:'fixture-csrf',principal:{role:'${role}',project_ids:['sample-api'],display_name:'Synthetic operator'}};window.location.hash='#/jobs?project_id=sample-api&job_id=${job.job_id}';jobsViewGeneration=7;document.querySelector('#app').replaceChildren(renderJobDetail(document.querySelector('#app'),reviewFixture));`,a.context);
  return a;
}
function candidateReview(overrides={}){return {candidate:{...candidate,...overrides},evidence_binding:null};}
function exportHeaders(overrides={}){return {'Content-Type':media,'X-ForgeGate-Job-Result':job.result_fingerprint,'X-ForgeGate-Assembly':assembly.assembly_id,'X-ForgeGate-Assembly-Fingerprint':assemblyFingerprint,...overrides};}
function bindingResponse(){return {schema_version:'forgegate.dashboard-job-evidence-binding.v1',job_id:job.job_id,result_fingerprint:job.result_fingerprint,assembly_id:assembly.assembly_id,assembly_fingerprint:assemblyFingerprint,binding:{binding_id:fp('4'),candidate_fingerprint:job.candidate_fingerprint,assembly_fingerprint:assemblyFingerprint,assembly},candidate_transition:'NOT_PERFORMED',policy_decision:'NOT_PERFORMED',source_artifact_bytes:'not_embedded'};}

test('terminal assembly exposes separately reviewed export and binding actions',async()=>{
  const a=await setup();
  assert.ok(find(a,'Review assembly download'));assert.ok(find(a,'Review evidence binding from task'));
  assert.match(a.root.text,/Source report bytes are not embedded/);assert.doesNotMatch(a.root.text,/Confirm evidence binding/);
});

test('canonical download freezes identities, verifies bytes and changes no state',async()=>{
  const a=await setup();await click(a,'Review assembly download');
  assert.equal(a.requests.length,1);assert.match(a.root.text,/changes no state/);assert.match(a.root.text,/Evidence records 1/);
  a.responses.push({status:200,headers:exportHeaders(),bytes});await click(a,'Download canonical assembly');
  assert.equal(a.requests.length,2);const request=a.requests.at(-1),body=JSON.parse(request.options.body);
  assert.match(request.path,/\/assembly-export\?project_id=sample-api$/);assert.equal(request.options.headers['X-ForgeGate-CSRF'],'fixture-csrf');
  assert.deepEqual(body,{expected_job_revision:2,expected_result_fingerprint:job.result_fingerprint,expected_assembly_id:assembly.assembly_id});
  assert.match(a.root.text,/Exact bytes verified/);assert.match(a.root.text,new RegExp(assemblyFingerprint));
  const download=all(a.root,'a').find(link=>link.download);assert.ok(download);assert.equal(download.download,`evidence-assembly-${'c'.repeat(64)}.json`);
});

test('closing assembly review makes no request',async()=>{const a=await setup();await click(a,'Review assembly download');await click(a,'Cancel');assert.equal(a.requests.length,1);});

for(const mode of ['media','job','assembly','fingerprint','bytes','oversize'])test(`assembly download rejects ${mode} mismatch without retry`,async()=>{
  const a=await setup();await click(a,'Review assembly download');
  const headers=exportHeaders();let output=bytes;
  if(mode==='media')headers['Content-Type']='application/json';
  if(mode==='job')headers['X-ForgeGate-Job-Result']=fp('9');
  if(mode==='assembly')headers['X-ForgeGate-Assembly']=fp('9');
  if(mode==='fingerprint')headers['X-ForgeGate-Assembly-Fingerprint']=fp('9');
  if(mode==='bytes')output=new TextEncoder().encode('changed');
  if(mode==='oversize')headers['Content-Length']='33554433';
  a.responses.push({status:200,headers,bytes:output});await click(a,'Download canonical assembly');
  assert.equal(a.requests.length,2);assert.match(a.root.text,/DASHBOARD_EXPORT_RESPONSE_INVALID/);assert.equal(find(a,'Download canonical assembly'),undefined);
});

test('job binding fetches current candidate then submits one frozen identity set',async()=>{
  const a=await setup();a.responses.push({status:200,body:candidateReview()});await click(a,'Review evidence binding from task');
  assert.equal(a.requests.length,2);assert.match(a.root.text,/does not rerun parsing/);assert.match(a.root.text,new RegExp(job.candidate_fingerprint));
  let finish;a.responses.push(()=>new Promise(resolve=>{finish=resolve;}));const confirm=find(a,'Confirm evidence binding');confirm.click();confirm.click();await flush();
  assert.equal(a.requests.length,3);const request=a.requests.at(-1),body=JSON.parse(request.options.body);
  assert.match(request.path,/\/bind-evidence\?project_id=sample-api$/);assert.equal(request.options.headers.get('X-ForgeGate-CSRF'),'fixture-csrf');assert.ok(request.options.headers.get('Idempotency-Key'));
  assert.equal(body.expected_job_revision,2);assert.equal(body.expected_result_fingerprint,job.result_fingerprint);assert.equal(body.expected_assembly_id,assembly.assembly_id);assert.equal(body.expected_candidate_revision,1);assert.equal(body.expected_candidate_fingerprint,job.candidate_fingerprint);
  finish({status:200,body:bindingResponse()});await flush();assert.match(a.root.text,/candidate was not advanced to READY/);assert.ok(all(a.root,'a').some(link=>link.text==='Review bound evidence'));
});

test('binding dialog cannot be dismissed while the write outcome is unknown',async()=>{
  const a=await setup();a.responses.push({status:200,body:candidateReview()});await click(a,'Review evidence binding from task');
  let finish;a.responses.push(()=>new Promise(resolve=>{finish=resolve;}));find(a,'Confirm evidence binding').click();await flush();find(a,'Back without binding').click();
  assert.match(a.root.text,/Submitting the frozen job/);finish({status:200,body:bindingResponse()});await flush();assert.match(a.root.text,/Binding completed/);
});

for(const mode of ['result','assembly-fingerprint','source-boundary'])test(`binding rejects ${mode} response mismatch without retry`,async()=>{
  const a=await setup();a.responses.push({status:200,body:candidateReview()});await click(a,'Review evidence binding from task');const response=bindingResponse();
  if(mode==='result')response.result_fingerprint=fp('9');
  if(mode==='assembly-fingerprint')response.assembly_fingerprint=fp('9');
  if(mode==='source-boundary')response.source_artifact_bytes='embedded';
  a.responses.push({status:200,body:response});await click(a,'Confirm evidence binding');assert.equal(a.requests.length,3);assert.ok(all(a.root,'a').some(link=>link.text==='Inspect candidate evidence'));
});

test('back from binding review performs only the candidate read',async()=>{const a=await setup();a.responses.push({status:200,body:candidateReview()});await click(a,'Review evidence binding from task');await click(a,'Back without binding');assert.equal(a.requests.length,2);});

for(const state of ['READY','PASS'])test(`stale ${state} candidate cannot expose a binding write`,async()=>{
  const a=await setup();a.responses.push({status:200,body:candidateReview({status:state,revision:2})});await click(a,'Review evidence binding from task');assert.equal(find(a,'Confirm evidence binding'),undefined);assert.match(a.root.text,/No binding request was sent/);assert.equal(a.requests.length,2);
});

test('already-bound candidate links to evidence without replacement write',async()=>{
  const a=await setup();const current=candidateReview();current.evidence_binding={assembly};a.responses.push({status:200,body:current});await click(a,'Review evidence binding from task');
  assert.equal(find(a,'Confirm evidence binding'),undefined);assert.match(a.root.text,/already has an immutable evidence binding/);assert.ok(all(a.root,'a').some(link=>link.text==='Review current candidate evidence'));
});

for(const status of [409,500,503])test(`binding HTTP ${status} offers inspection without retry`,async()=>{
  const a=await setup();a.responses.push({status:200,body:candidateReview()});await click(a,'Review evidence binding from task');a.responses.push({status,body:{error:{code:'FIXTURE_BIND_ERROR',message:'stale',request_id:'fixture-request'}}});await click(a,'Confirm evidence binding');
  assert.equal(a.requests.length,3);assert.match(a.root.text,/FIXTURE_BIND_ERROR/);assert.equal(find(a,'Confirm evidence binding'),undefined);assert.ok(all(a.root,'a').some(link=>link.text==='Inspect candidate evidence'));
});

test('late binding response after logout cannot reveal completed binding',async()=>{
  const a=await setup();a.responses.push({status:200,body:candidateReview()});await click(a,'Review evidence binding from task');let finish;a.responses.push(()=>new Promise(resolve=>{finish=resolve;}));find(a,'Confirm evidence binding').click();await flush();runInContext('session=null;renderActivation()',a.context);finish({status:200,body:bindingResponse()});await flush();assert.doesNotMatch(a.root.text,/Review bound evidence/);
});

test('producer and non-SUCCEEDED results expose neither result action',async()=>{
  const producer=await setup('producer');assert.equal(find(producer,'Review assembly download'),undefined);assert.equal(find(producer,'Review evidence binding from task'),undefined);
  const warning=await setup('operator',{...review,record:{...job,state:'REVIEW_REQUIRED'}});assert.equal(find(warning,'Review assembly download'),undefined);assert.equal(find(warning,'Review evidence binding from task'),undefined);
});
