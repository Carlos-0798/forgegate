import assert from "node:assert/strict";
import { test } from "node:test";
import { runInContext } from "node:vm";
import { createHash } from "node:crypto";
import { harness, flush } from "./harness.mjs";

const hashes = ["source", "receipt"].map(x => createHash("sha256").update(x).digest("hex"));
const all = (node, tag) => [...(node.tag === tag ? [node] : []), ...node.children.flatMap(x => all(x, tag))];
async function start() {
  const a = await harness();
  a.context.review = {candidate:{candidate_id:"cand-"+"a".repeat(24),commit_sha:"a".repeat(40),revision:4,status:"FAIL"},assurance_bundle_id:"sha256:"+"b".repeat(64),evidence_binding:{assembly:{collections:[{source:{sha256:hashes[1],size_bytes:7},artifacts:[{sha256:hashes[0],size_bytes:6}]}]}}};
  runInContext("session={csrf_token:'fixture',principal:{role:'operator'}}; openReplayExportDialog(document.querySelector('#app'),review);",a.context);
  a.dialog = a.root.querySelector("dialog");
  [a.input,a.consent] = all(a.dialog,"input");
  a.input.files = ["source","receipt"].map(x=>({name:x,size:x.length,arrayBuffer:async()=>new TextEncoder().encode(x).buffer}));
  return a;
}
async function click(a,name) { const b=all(a.dialog,"button").find(x=>x.textContent===name); assert.ok(b,name); await b.listeners.click[0](); await flush(); }
test("replay export requires reviewed hashes and privacy consent, preserves bytes",async()=>{
  const a=await start(); await click(a,"Review selected originals");
  await click(a,"Confirm private replay download"); assert.equal(a.requests.length,1);
  assert.match(a.dialog.text,/acknowledge/); a.consent.checked=true;
  a.responses.push({status:409,body:{error:{code:"STORE_REVISION_CONFLICT",message:"reload"}}});
  await click(a,"Confirm private replay download");
  const body=JSON.parse(a.requests.at(-1).options.body);
  assert.equal(body.expected_revision,4); assert.equal(body.acknowledge_private_sources,true);
  assert.deepEqual(body.files.map(x=>Buffer.from(x.content_base64,"base64").toString()),["source","receipt"]);
  assert.match(a.dialog.text,/STORE_REVISION_CONFLICT/);
  assert.equal(all(a.dialog,"button").some(x=>x.textContent==="Confirm private replay download"),false);
});
for(const failure of ["missing","duplicate","oversize","changed","unknown"]) test(`replay ${failure} selection never submits`,async()=>{
  const a=await start();
  if(failure==="missing") a.input.files.pop();
  if(failure==="duplicate") a.input.files[1]=a.input.files[0];
  if(failure==="oversize") a.input.files[0].size=1048577;
  if(failure==="changed") a.input.files[0].size++;
  if(failure==="unknown") a.input.files[0].arrayBuffer=async()=>new TextEncoder().encode("forged").buffer;
  await click(a,"Review selected originals"); assert.equal(a.requests.length,1);
  assert.match(a.dialog.text,/DASHBOARD_REPLAY_SELECTION_INVALID/);
  assert.equal(a.input.disabled,false);
  assert.equal(all(a.dialog,"button").some(x=>x.textContent==="Confirm private replay download"),false);
});
test("closing during file reading prevents a late review or export",async()=>{
  const a=await start(); let resolve;
  a.input.files[0].arrayBuffer=()=>new Promise(r=>{resolve=r;});
  const pending=click(a,"Review selected originals"); await flush();
  await click(a,"Cancel"); resolve(new TextEncoder().encode("source").buffer); await pending;
  assert.equal(a.requests.length,1); assert.equal(a.dialog.isConnected,false);
});
for(const status of [413,429,500]) test(`replay HTTP ${status} has no automatic retry`,async()=>{
  const a=await start(); await click(a,"Review selected originals"); a.consent.checked=true;
  a.responses.push({status,body:{error:{code:"TEST_REFUSAL",message:"controlled error"}}});
  await click(a,"Confirm private replay download"); assert.equal(a.requests.length,2);
  assert.match(a.dialog.text,/TEST_REFUSAL/);
});

test("prepared originals need no reselection and still require privacy consent",async()=>{
  const a=await start();a.dialog.close();a.context.prepared=a.input.files;
  runInContext("openReplayExportDialog(document.querySelector('#app'),review,undefined,prepared)",a.context);
  a.dialog=all(a.root,"dialog").at(-1);[a.input,a.consent]=all(a.dialog,"input");
  assert.match(a.dialog.text,/2 original source files \(reports plus exact collection receipts\)/);
  assert.equal(a.input.disabled,true);await click(a,"Review selected originals");
  await click(a,"Confirm private replay download");assert.equal(a.requests.length,1);
  assert.match(a.dialog.text,/acknowledge/);
});

test("session change after replay review prevents upload",async()=>{
  const a=await start();await click(a,"Review selected originals");a.consent.checked=true;
  runInContext("session=null",a.context);await click(a,"Confirm private replay download");
  assert.equal(a.requests.length,1);
});
