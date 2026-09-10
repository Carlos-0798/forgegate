import assert from "node:assert/strict";
import { test } from "node:test";
import { runInContext } from "node:vm";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { harness, flush } from "./harness.mjs";

const names = ["tests.xml","coverage.xml","clean.sarif","benchmark.json"];
const files = names.map(name => readFileSync(new URL("../../examples/dashboard-standard-ci/" + name, import.meta.url)));
const candidate = {candidate_id:"cand-"+"a".repeat(24),project_id:"sample-api",commit_sha:"a".repeat(40),revision:1,status:"COLLECTING"};
const all = (node, tag) => [...(node.tag===tag?[node]:[]),...node.children.flatMap(child=>all(child,tag))];
const find = (a,label) => all(a.dialog,"button").find(b=>b.textContent===label);
async function click(a,label) { const b=find(a,label); assert.ok(b,label); await b.listeners.click[0](); await flush(); }
async function app(durable=false) {
  const a=await harness(); a.context.fixture=candidate; a.context.durable=durable;
  runInContext("session={csrf_token:'fixture',principal:{role:'operator'}}; openJUnitImport(document.querySelector('#app'),fixture,undefined,true,durable);",a.context);
  const dialog=a.root.querySelector("dialog"), form=dialog.querySelector("form"); form.reportValidity=()=>true;
  const inputs=all(form,"input");
  for (const [i,pos] of [0,5,9,11].entries()) inputs[pos].files=[{name:names[i],size:files[i].length,arrayBuffer:async()=>Uint8Array.from(files[i]).buffer}];
  for(const i of [2,6]) inputs[i].value="synthetic";
  for(const i of [3,7]) inputs[i].value="1";
  for(const i of [4,8,10,12]) inputs[i].value="2026-09-04T12:00:00Z";
  form.querySelector("select").value="coverage_xml";
  return {...a,dialog,form,inputs};
}
function response() {
  const assembly={schema_version:"forgegate.evidence-bundle-assembly.v1",assembly_id:"sha256:synthetic",bundle:{candidate_commit:candidate.commit_sha,evidence:[{},{},{},{}]},collections:[{},{},{},{}],warning_disposition:"none"};
  return {status:200,body:{schema_version:"forgegate.dashboard-collection-preview.v1",candidate_id:candidate.candidate_id,expected_revision:1,assembly,assembly_json:JSON.stringify(assembly),collections:files.map(data=>({status:"COMPLETE",artifacts:[{sha256:createHash("sha256").update(data).digest("hex"),size_bytes:data.length}],evidence:[],warnings:[],rejected_records:[]}))}};
}
for(const durable of [false,true]) test(`four reports preserve bytes through reviewed ${durable?"task":"binding"}`,async()=>{
  const a=await app(durable); a.responses.push(response()); await click(a,"Preview reports — no binding");
  const body=JSON.parse(a.requests.at(-1).options.body);
  assert.deepEqual(body.reports.map(r=>r.format),["junit","coverage_xml","sarif","benchmark_json"]);
  body.reports.forEach((r,i)=>assert.deepEqual(Buffer.from(r.content_base64,"base64"),files[i]));
  assert.equal(body.reports[2].source_tool,"report-embedded");
  await click(a,durable?"Review durable submission":"Review immutable binding"); assert.equal(a.requests.length,2);
  assert.match(a.dialog.text,/sarif/); assert.match(a.dialog.text,/benchmark_json/);
  a.responses.push({status:200,body:durable?{job_id:"job-"+"b".repeat(32),candidate_id:candidate.candidate_id,project_id:"sample-api",revision:0,state:"QUEUED"}:{binding_id:"binding-fixture"}});
  await click(a,durable?"Confirm task submission":"Confirm evidence binding");
  assert.match(a.requests.at(-1).path,durable?/\/jobs\?project_id=sample-api$/:/evidence$/);
  const submitted=JSON.parse(a.requests.at(-1).options.body);
  assert.equal(durable?submitted.collection.reports.length:submitted.assembly.collections.length,4);
});
for(const kind of ["missing-time","orphan-time","future","oversize","total-size","duplicate","changed-size"]) test(`supplement ${kind} makes no HTTP request`,async()=>{
  const a=await app();
  if(kind==="missing-time") a.inputs[10].value="";
  if(kind==="orphan-time") a.inputs[9].files=[];
  if(kind==="future") a.inputs[12].value="2999-01-01T00:00:00Z";
  if(kind==="oversize") a.inputs[11].files[0].size=1048577;
  if(kind==="total-size") for(const p of [0,5,9,11]) a.inputs[p].files[0].size=600000;
  if(kind==="duplicate") a.inputs[9].files=a.inputs[0].files;
  if(kind==="changed-size") a.inputs[11].files[0].size++;
  await click(a,"Preview reports — no binding");
  assert.equal(a.requests.length,1); assert.equal(find(a,"Review immutable binding"),undefined);
  assert.match(a.dialog.text,/DASHBOARD_COLLECTION_INVALID/);
});
test("a rejected security report prevents binding of the other three reports",async()=>{
  const a=await app(), r=response(); r.body.collections[2].status="REJECTED"; r.body.assembly=null; r.body.assembly_json=null;
  a.responses.push(r); await click(a,"Preview reports — no binding");
  assert.equal(find(a,"Review immutable binding"),undefined);
  assert.equal(find(a,"Retain these warnings and preview again"),undefined);
});
