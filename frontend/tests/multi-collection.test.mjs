import assert from "node:assert/strict";
import { test } from "node:test";
import { runInContext } from "node:vm";
import { createHash } from "node:crypto";
import { harness, flush } from "./harness.mjs";

const texts = ['<testsuite tests="4"/>', 'SF:demo.c\nDA:1,1\nend_of_record\n'];
const bytes = texts.map((text) => new TextEncoder().encode(text));
const hashes = bytes.map((value) => createHash("sha256").update(value).digest("hex"));
const candidate = {candidate_id: `cand-${"a".repeat(24)}`, commit_sha: "b".repeat(40), revision: 1, status: "COLLECTING"};
const assembly = {schema_version:"forgegate.evidence-bundle-assembly.v1", assembly_id:"sha256:fixture", bundle:{candidate_commit:candidate.commit_sha,evidence:[{},{}]},collections:[{},{}],warning_disposition:"none"};
const all = (node, tag) => [...(node.tag === tag ? [node] : []), ...node.children.flatMap((child) => all(child, tag))];
const find = (a, label) => all(a.dialog,"button").find((b) => b.textContent === label);
async function click(a, label) { const b = find(a,label); assert.ok(b,label); await b.listeners.click[0](); await flush(); }
function response() {
  return {status:200,body:{schema_version:"forgegate.dashboard-collection-preview.v1",candidate_id:candidate.candidate_id,expected_revision:1,assembly,assembly_json:JSON.stringify(assembly),
    collections:bytes.map((value,index) => ({status:"COMPLETE",artifacts:[{sha256:hashes[index],size_bytes:value.length}],evidence:[{value:index ? {covered:1,total:2,percent:50} : {total:4,passed:4}}],warnings:[],rejected_records:[]}))}};
}
async function app() {
  const a = await harness(); a.context.fixture = candidate;
  runInContext("session={csrf_token:'fixture',principal:{role:'operator'}}; openJUnitImport(document.querySelector('#app'),fixture,undefined,true);",a.context);
  const dialog = a.root.querySelector("dialog"), form = dialog.querySelector("form"); form.reportValidity=()=>true;
  const inputs = all(form,"input");
  for (const [index, position] of [0,5].entries()) inputs[position].files=[{name:index ? "coverage.info" : "tests.xml",size:bytes[index].length,arrayBuffer:async()=>bytes[index].buffer}];
  for (const i of [2,6]) inputs[i].value="synthetic-tool";
  for (const i of [3,7]) inputs[i].value="1";
  inputs[4].value="2026-01-01T00:00:00Z"; inputs[8].value="2026-01-02T00:00:00Z";
  form.querySelector("select").value="lcov";
  return {...a,dialog,form,inputs};
}
test("combined exact-byte preview preserves separate times and requires explicit binding",async()=>{
  const a=await app(); a.responses.push(response()); await click(a,"Preview reports — no binding");
  const request=a.requests.at(-1), body=JSON.parse(request.options.body);
  assert.match(request.path,/collection-preview$/); assert.equal(body.reports.length,2);
  body.reports.forEach((report,index)=>assert.equal(Buffer.from(report.content_base64,"base64").toString(),texts[index]));
  assert.equal(body.reports[1].collected_at,"2026-01-02T00:00:00Z"); assert.equal(body.reports[1].format,"lcov");
  assert.match(a.dialog.text,/"percent": 50/); assert.equal(a.requests.length,2);
  await click(a,"Review immutable binding"); assert.equal(a.requests.length,2);
  assert.match(a.dialog.text,/Coverage report SHA-256/); assert.match(a.dialog.text,new RegExp(hashes[1]));
  a.responses.push({status:200,body:{binding_id:"fixture"}}); await click(a,"Confirm evidence binding");
  assert.match(a.requests.at(-1).path,/\/evidence$/); assert.equal(JSON.parse(a.requests.at(-1).options.body).assembly.collections.length,2);
});
for (const kind of ["missing","oversize","empty","time","future","duplicate","format"]) test(`invalid coverage ${kind} performs no preview`,async()=>{
  const a=await app();
  if(kind==="missing") a.inputs[5].files=[];
  if(kind==="oversize") a.inputs[5].files[0].size=1048577;
  if(kind==="empty") a.inputs[5].files[0].size=0;
  if(kind==="time") a.inputs[8].value="2026-01-01";
  if(kind==="future") a.inputs[8].value="2999-01-01T00:00:00Z";
  if(kind==="duplicate") a.inputs[5].files[0]=a.inputs[0].files[0];
  if(kind==="format") a.form.querySelector("select").value="sarif";
  await click(a,"Preview reports — no binding"); assert.equal(a.requests.length,1); assert.equal(find(a,"Review immutable binding"),undefined);
});
for (const mismatch of ["count","hash","size","identity"]) test(`mismatched combined ${mismatch} is not bindable`,async()=>{
  const a=await app(), r=response();
  if(mismatch==="count") r.body.collections.pop();
  if(mismatch==="hash") r.body.collections[1].artifacts[0].sha256="0".repeat(64);
  if(mismatch==="size") r.body.collections[1].artifacts[0].size_bytes++;
  if(mismatch==="identity") r.body.expected_revision=2;
  a.responses.push(r); await click(a,"Preview reports — no binding"); assert.equal(find(a,"Review immutable binding"),undefined);
});
test("one rejected report cannot expose a partial assembly or warning override",async()=>{
  const a=await app(), r=response(); r.body.collections[1].status="REJECTED"; r.body.collections[1].rejected_records=[{code:"BAD",message:"<img src=x>"}];
  a.responses.push(r); await click(a,"Preview reports — no binding"); assert.equal(find(a,"Review immutable binding"),undefined); assert.equal(find(a,"Retain these warnings and preview again"),undefined); assert.equal(a.dialog.querySelector("img"),null);
});
test("warning consent replays the same complete report selection once",async()=>{
  const a=await app(), r=response(); r.body.assembly=null; r.body.collections[1].warnings=[{code:"SUMMARY",message:"summary only"}];
  a.responses.push(r); await click(a,"Preview reports — no binding"); const before=JSON.parse(a.requests.at(-1).options.body);
  a.responses.push(response()); await click(a,"Retain these warnings and preview again"); const after=JSON.parse(a.requests.at(-1).options.body);
  assert.deepEqual(after.reports,before.reports); assert.equal(after.retain_warnings,true); assert.ok(find(a,"Review immutable binding"));
});
test("bounded visible issues cannot hide warnings behind consent",async()=>{
  const a=await app(), r=response(); r.body.assembly=null; r.body.collections[1].warnings=Array.from({length:26},()=>({code:"WARN",message:"detail"}));
  a.responses.push(r); await click(a,"Preview reports — no binding"); assert.match(a.dialog.text,/Showing 25 of 26 issues/); assert.equal(find(a,"Retain these warnings and preview again"),undefined);
});
test("binding retains original floating point lexemes and large integers",async()=>{
  const a=await app(), r=response();
  r.body.assembly_json=JSON.stringify(assembly).replace('"evidence":[{},{}]', '"evidence":[{"value":{"percent":50.0,"large":9007199254740993}},{}]');
  r.body.assembly=JSON.parse(r.body.assembly_json);
  a.responses.push(r); await click(a,"Preview reports — no binding"); await click(a,"Review immutable binding");
  a.responses.push({status:200,body:{binding_id:"fixture"}}); await click(a,"Confirm evidence binding");
  const sent=a.requests.at(-1).options.body;
  assert.ok(sent.includes('"percent":50.0')); assert.ok(sent.includes('"large":9007199254740993'));
});
for (const kind of ["missing","different"]) test(`exact assembly ${kind} blocks binding`,async()=>{
  const a=await app(), r=response(); r.body.assembly_json=kind==="missing" ? undefined : "{}";
  a.responses.push(r); await click(a,"Preview reports — no binding"); assert.equal(find(a,"Review immutable binding"),undefined);
});
for(const field of ["assembly","policy_material"]) test(`exact document envelope preserves ${field} without number coercion`,async()=>{
  const a=await harness();
  a.context.rawDocument='{"expected":50.0,"count":9007199254740993,"literal":"quoted\\\" text"}';
  a.context.field=field;
  const body=runInContext('exactDocumentBody({[field]:JSON.parse(rawDocument),bound_at:"2026-01-01T00:00:00Z"},field,rawDocument)',a.context);
  assert.ok(body.includes('"expected":50.0')); assert.ok(body.includes('"count":9007199254740993'));
  assert.equal(JSON.parse(body).bound_at,"2026-01-01T00:00:00Z");
  assert.deepEqual(JSON.parse(body)[field],JSON.parse(a.context.rawDocument));
});
for (const action of ["close","logout","navigate"]) test(`late combined response after ${action} is discarded`,async()=>{
  const a=await app(); let finish; a.responses.push(()=>new Promise((resolve)=>{finish=resolve;}));
  const pending=click(a,"Preview reports — no binding"); while(!finish) await flush();
  if(action==="close") a.dialog.close();
  if(action==="logout") runInContext("session=null",a.context);
  if(action==="navigate") runInContext("window.location.hash='#/overview'",a.context);
  finish(response()); await pending; assert.equal(find(a,"Review immutable binding"),undefined);
});
for(const code of [401,409,413,422,429,500]) test(`combined HTTP ${code} does not retry or bind`,async()=>{
  const a=await app(); a.responses.push({status:code}); await click(a,"Preview reports — no binding"); assert.equal(a.requests.length,2); assert.equal(find(a,"Review immutable binding"),undefined);
});
