import assert from "node:assert/strict";
import {test} from "node:test";
import {runInContext} from "node:vm";
import {createHash} from "node:crypto";
import {readFileSync} from "node:fs";
import {harness, flush} from "./harness.mjs";

const root = new URL("../../examples/dashboard-standard-ci/", import.meta.url);
const bytes = ["tests.xml", "coverage.xml", "clean.sarif", "benchmark.json"].map(name => readFileSync(new URL(name, root)));
const file = (data, name="neutral.dat") => ({name,size:data.length,arrayBuffer:async()=>Uint8Array.from(data).buffer});
const candidate = {candidate_id:"cand-"+"a".repeat(24),project_id:"sample-api",version:"test",commit_sha:"a".repeat(40),release_track:"pull-request",project_profile_id:"profile",project_profile_version:1,revision:1,status:"COLLECTING"};
const material = {schema_version:"forgegate.policy-material.v1",release_track:"pull-request",project_profile_id:"profile",project_profile_version:1,policy:{name:"fixture",rules:[]}};
const all=(node,tag)=>[...(node.tag===tag?[node]:[]),...node.children.flatMap(child=>all(child,tag))];
const find=(a,label)=>all(a.dialog,"button").find(b=>b.textContent===label);
async function click(a,label){const button=find(a,label);assert.ok(button,label);await button.listeners.click[0]();await flush();}
async function setup(state="COLLECTING") {
  const a=await harness();a.context.fixture={...candidate,status:state,revision:state==="DRAFT"?0:1};
  runInContext("session={csrf_token:'fixture',principal:{role:'operator'}};openQuickAssessment(document.querySelector('#app'),fixture);",a.context);
  a.dialog=a.root.querySelector("dialog");a.form=a.dialog.querySelector("form");a.form.reportValidity=()=>true;
  a.inputs=Object.fromEntries(all(a.form,"input").map(input=>[input.name,input]));
  a.inputs["quick-files"].files=bytes.map((data,index)=>file(data,`neutral-${index}.dat`));
  a.inputs["quick-policy"].files=[file(Buffer.from(JSON.stringify(material)),"policy.json")];
  a.inputs["quick-tool"].value="synthetic";a.inputs["quick-tool-version"].value="1";a.inputs["quick-time"].value="2026-09-01T12:00:00Z";
  return a;
}
function preview() {
  const assembly={schema_version:"forgegate.evidence-bundle-assembly.v1",bundle:{candidate_commit:candidate.commit_sha,evidence:[]},collections:[]};
  return {status:200,body:{schema_version:"forgegate.dashboard-collection-preview.v1",candidate_id:candidate.candidate_id,expected_revision:1,assembly,assembly_json:JSON.stringify(assembly),collections:bytes.map(data=>({status:"COMPLETE",artifacts:[{sha256:createHash("sha256").update(data).digest("hex"),size_bytes:data.length}],evidence:[],warnings:[],rejected_records:[]}))}};
}
function chain(decision="FAIL") {
  const terminal={...candidate,status:decision,revision:4,evaluation_id:"evaluation"};
  return [{status:200,body:{}},...[["READY",2],["EVALUATING",3]].map(([status,revision])=>({status:200,body:{candidate:{...candidate,status,revision}}})),{status:200,body:{}},{status:200,body:{candidate:terminal}},{status:200,body:{attestation_id:"attestation"}},{status:200,body:{candidate:terminal,attestation:{attestation_id:"attestation"},assurance_bundle_id:"bundle"}}];
}
for(const decision of ["PASS","FAIL","REVIEW","ERROR"]) test(`batch reaches actual ${decision} and offers reviewed export`,async()=>{
  const a=await setup("DRAFT");a.responses.push({status:200,body:{candidate}},preview());
  a.responses.at(-1).body.collections[0].evidence=[{kind:"test.summary",scope:"suite",value:{tests:4,failures:0}}];
  await click(a,"Start collection and preview");
  assert.match(a.dialog.text,/test\.summary · suite/);
  assert.deepEqual(JSON.parse(a.requests.at(-1).options.body).reports.map(r=>r.format),["junit","coverage_xml","sarif","benchmark_json"]);
  assert.equal(a.requests.length,3); // initial session, transition, read-only preview
  a.responses.push(...chain(decision));await click(a,"Confirm assessment and attestation");
  assert.match(a.dialog.text,new RegExp(`Engineering decision: ${decision}`));
  assert.ok(find(a,"Review assurance download"));
  assert.equal(a.requests.length,10);
  assert.ok(all(a.dialog,"a").some(link=>link.href.includes("candidate_id=")));
});
for(const stage of [0,1,2,3,4,5,6]) test(`failure at chain step ${stage} stops all following operations`,async()=>{
  const a=await setup();a.responses.push(preview());await click(a,"Preview batch");
  const responses=chain();responses[stage]={status:stage===1?409:500};a.responses.push(...responses.slice(0,stage+1));
  await click(a,"Confirm assessment and attestation");assert.equal(a.requests.length,3+stage);
  assert.equal(find(a,"Review assurance download"),undefined);assert.equal(find(a,"Confirm assessment and attestation"),undefined);
  assert.match(a.dialog.text,/Completed steps remain retained/);
});
for(const kind of ["duplicate","oversize","unknown","changed","policy-profile","future","both"]) test(`${kind} rejected before candidate writes`,async()=>{
  const a=await setup("DRAFT");
  if(kind==="duplicate")a.inputs["quick-files"].files=[file(bytes[0]),file(bytes[0])];
  if(kind==="oversize")a.inputs["quick-files"].files[0].size=1048577;
  if(kind==="unknown")a.inputs["quick-files"].files=[file(Buffer.from("unrecognized"))];
  if(kind==="changed")a.inputs["quick-files"].files[0].size++;
  if(kind==="policy-profile")a.inputs["quick-policy"].files=[file(Buffer.from(JSON.stringify({...material,project_profile_id:"wrong"})))];
  if(kind==="future")a.inputs["quick-time"].value="2999-01-01T00:00:00Z";
  if(kind==="both")a.inputs["quick-folder"].files=a.inputs["quick-files"].files;
  await click(a,"Start collection and preview");assert.equal(a.requests.length,1);assert.equal(find(a,"Confirm assessment and attestation"),undefined);
});
for(const kind of ["hash","rejection","warning","assembly"]) test(`preview ${kind} stops before binding`,async()=>{
  const a=await setup(),response=preview();
  if(kind==="hash")response.body.collections[0].artifacts[0].sha256="wrong";
  if(kind==="rejection")response.body.collections[0].status="REJECTED";
  if(kind==="warning")response.body.collections[0].warnings=[{code:"WARNING",message:"Review required"}];
  if(kind==="assembly")response.body.assembly_json="{}";
  a.responses.push(response);await click(a,"Preview batch");assert.equal(a.requests.length,2);assert.equal(find(a,"Confirm assessment and attestation"),undefined);
  if(kind === "rejection") {
    assert.match(a.dialog.text,/DASHBOARD_QUICK_REPORT_REVIEW_REQUIRED/);
    assert.doesNotMatch(a.dialog.text,/DASHBOARD_UNEXPECTED_ERROR/);
  }
});
test("session change after binding prevents further transitions",async()=>{
  const a=await setup();a.responses.push(preview());await click(a,"Preview batch");
  a.responses.push(()=>{runInContext("session=null",a.context);return {status:200,body:{}};});
  await click(a,"Confirm assessment and attestation");assert.equal(a.requests.length,3);
});
test("double confirmation only starts one chain",async()=>{
  const a=await setup();a.responses.push(preview());await click(a,"Preview batch");a.responses.push(...chain());
  const handler=find(a,"Confirm assessment and attestation").listeners.click[0];await Promise.all([handler(),handler()]);assert.equal(a.requests.length,9);
});
test("folder input and LCOV are identified from content",async()=>{
  const a=await setup();a.context.reportBytes=new TextEncoder().encode("TN:fixture\nSF:module.c\nDA:1,1\nend_of_record\n").buffer;
  assert.equal(runInContext("detectQuickReport(reportBytes)",a.context),"lcov");
  a.inputs["quick-folder"].files=a.inputs["quick-files"].files;a.inputs["quick-files"].files=[];
  a.responses.push(preview());await click(a,"Preview batch");assert.ok(find(a,"Confirm assessment and attestation"));
});

test("saved policy selection preserves exact number spelling in evaluation",async()=>{
  const a=await setup();
  const text=JSON.stringify({...material,material_id:"sha256:"+"f".repeat(64),policy:{name:"fixture",rules:[],threshold:42.75}}).replace('42.75','42.750');
  a.responses.push({status:200,body:{candidate_id:candidate.candidate_id,choices:[{material:JSON.parse(text),material_json:text}],truncated:false}});
  await click(a,"Load saved policies");
  const select=all(a.form,"select")[0];select.value="sha256:"+"f".repeat(64);select.listeners.change[0]();
  a.inputs["quick-policy"].files=[];a.responses.push(preview());await click(a,"Preview batch");
  a.responses.push(...chain());await click(a,"Confirm assessment and attestation");
  assert.ok(a.requests.some(r=>r.options?.body?.includes('42.750')));
});

for(const kind of ["wrong-profile","mismatched-bytes","late-session"]) test(`saved policy ${kind} cannot become a choice`,async()=>{
  const a=await setup();const value={...material,material_id:"saved"};
  if(kind==="wrong-profile")value.project_profile_id="wrong";
  const response={status:200,body:{candidate_id:candidate.candidate_id,choices:[{material:value,material_json:kind==="mismatched-bytes"?"{}":JSON.stringify(value)}],truncated:false}};
  a.responses.push(kind==="late-session"?()=>{runInContext("session=null",a.context);return response;}:response);
  await click(a,"Load saved policies");assert.equal(all(a.form,"option").length,1);
  assert.equal(a.requests.length,2);
});

test("prepared replay keeps exact receipt bytes including decimal spelling",async()=>{
  const a=await harness();const report=Buffer.from("report"),receipt=Buffer.from('{"value":100.0}');
  const ref=data=>({sha256:createHash("sha256").update(data).digest("hex"),size_bytes:data.length});
  a.context.reports=[{bytes:Uint8Array.from(report).buffer,file:{name:"report.txt"}}];
  a.context.preview={collection_json:[receipt.toString()],assembly:{collections:[{source:ref(receipt),artifacts:[ref(report)]}]}};
  const files=await runInContext("quickReplayFiles(reports,preview)",a.context);
  assert.deepEqual(await Promise.all(files.map(f=>f.text())),["report",'{"value":100.0}']);
  a.context.preview.collection_json=['{"value":100}'];
  await assert.rejects(runInContext("quickReplayFiles(reports,preview)",a.context),/Exact original/);
});

test("quick assessment labels the combined report and receipt count accurately",async()=>{
  const a=await setup("DRAFT");
  a.inputs["quick-files"].files=[file(bytes[0],"single.xml")];
  const receipt=Buffer.from('{"status":"COMPLETE"}');
  const response=preview();
  response.body.collections=[response.body.collections[0]];
  response.body.collection_json=[receipt.toString()];
  response.body.assembly.collections=[{
    source:{sha256:createHash("sha256").update(receipt).digest("hex"),size_bytes:receipt.length},
    artifacts:[{sha256:createHash("sha256").update(bytes[0]).digest("hex"),size_bytes:bytes[0].length}]
  }];
  response.body.assembly_json=JSON.stringify(response.body.assembly);
  a.responses.push({status:200,body:{candidate}},response);await click(a,"Start collection and preview");
  assert.match(a.dialog.text,/2 original source files \(reports plus exact collection receipts\)/);
});

test("different report tools and times are submitted exactly",async()=>{
  const a=await setup();
  a.inputs["quick-tool"].value="pytest";a.inputs["quick-tool-version"].value="8.4.2";
  a.inputs["quick-coverage-tool"].value="coverage.py";a.inputs["quick-coverage-version"].value="7.16.0";
  a.inputs["quick-coverage-time"].value="2026-09-01T11:58:00Z";
  a.inputs["quick-sarif-time"].value="2026-09-01T11:59:00Z";
  a.responses.push(preview());await click(a,"Preview batch");
  const r=JSON.parse(a.requests.at(-1).options.body).reports;
  assert.deepEqual(r.map(x=>x.source_tool),["pytest","coverage.py","report-embedded","report-embedded"]);
  assert.equal(r[1].source_version,"7.16.0");assert.equal(r[1].collected_at,"2026-09-01T11:58:00Z");
  assert.equal(r[2].collected_at,"2026-09-01T11:59:00Z");assert.equal(r[3].collected_at,"2026-09-01T12:00:00Z");
});
for(const kind of ["missing-version","future-time","missing-offset"]) test(`invalid override ${kind} stops before writes`,async()=>{
  const a=await setup("DRAFT");
  if(kind==="missing-version")a.inputs["quick-coverage-tool"].value="coverage.py";
  else a.inputs["quick-coverage-time"].value=kind==="future-time"?"2999-01-01T00:00:00Z":"2026-09-01T12:00:00";
  await click(a,"Start collection and preview");assert.equal(a.requests.length,1);
});
function warningPreview(){const r=preview();r.body.collections[1].warnings=[{code:"COVERAGE_BRANCH_SUMMARY_ONLY",message:"Branches not measured"}];return r;}
test("warning retention requires review then a separate assessment confirmation",async()=>{
  const a=await setup();a.responses.push(warningPreview());await click(a,"Preview batch");
  assert.equal(find(a,"Confirm assessment and attestation"),undefined);
  await click(a,"Retain reviewed warnings and preview");assert.equal(a.requests.length,2);
  const consent=all(a.form,"input").find(i=>i.type==="checkbox");consent.checked=true;
  a.responses.push(warningPreview());await click(a,"Retain reviewed warnings and preview");
  assert.equal(JSON.parse(a.requests.at(-1).options.body).retain_warnings,true);
  assert.equal(a.requests.length,3);assert.ok(find(a,"Confirm assessment and attestation"));
  a.responses.push(...chain("FAIL"));await click(a,"Confirm assessment and attestation");
  assert.match(a.dialog.text,/Engineering decision: FAIL/);
});
for(const kind of ["changed-results","changed-receipts","session-change","request-failure"]) test(`warning review ${kind} never binds`,async()=>{
  const a=await setup();a.responses.push(warningPreview());await click(a,"Preview batch");
  all(a.form,"input").find(i=>i.type==="checkbox").checked=true;
  const next=warningPreview();
  if(kind==="changed-results")next.body.collections[1].warnings[0].message="different warning";
  if(kind==="changed-receipts")next.body.collection_json=["changed"];
  a.responses.push(kind==="request-failure"?{status:500}:kind==="session-change"?()=>{runInContext("session=null",a.context);return next;}:next);
  await click(a,"Retain reviewed warnings and preview");assert.equal(a.requests.length,3);
  assert.equal(find(a,"Confirm assessment and attestation"),undefined);
});
test("more than 25 warnings cannot be consented without full review",async()=>{
  const a=await setup(),r=warningPreview();r.body.collections[1].warnings=Array(26).fill(r.body.collections[1].warnings[0]);
  a.responses.push(r);await click(a,"Preview batch");assert.equal(find(a,"Retain reviewed warnings and preview"),undefined);
  assert.equal(find(a,"Confirm assessment and attestation"),undefined);
});
