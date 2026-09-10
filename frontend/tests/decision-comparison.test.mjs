import assert from "node:assert/strict";
import {test} from "node:test";
import {runInContext} from "node:vm";
import {harness, flush} from "./harness.mjs";

const rule = (decision="PASS", reason="THRESHOLD_MET", actual=0) => ({rule_id:"tests",claim:"tests.ok",decision,mandatory:true,expected:0,actual,evidence_ids:["record"],reason_code:reason,explanation:"Fixture result",remediation_hint:null});
const review = (id="baseline", result=rule()) => ({
  candidate:{candidate_id:id,project_id:"sample-api",version:id,commit_sha:"a".repeat(40),release_track:"pull-request",project_profile_id:"profile",project_profile_version:1,evaluation_id:`eval-${id}`,status:result.decision},
  policy_material:{material_id:"material",project_profile_id:"profile",project_profile_version:1,release_track:"pull-request",policy_fingerprint:"policy",artifact:{sha256:"bytes"},policy:{rules:[{id:"tests"}]}},
  policy_evaluation:{evaluation_id:`eval-${id}`,candidate_commit:"a".repeat(40),decision:result.decision,policy_material_id:"material",policy_fingerprint:"policy",project_profile_id:"profile",project_profile_version:1,rule_results:[result],evaluated_at:"2026-09-08T12:00:00Z"}
});
async function compare(before,after) {
  const a=await harness();a.context.before=before;a.context.after=after;
  return JSON.parse(JSON.stringify(runInContext("compareDecisions(before,after)",a.context)));
}
for(const [old,next,expected] of [["PASS","FAIL","New failure"],["FAIL","PASS","Rule restored to PASS"],["FAIL","REVIEW","Now REVIEW"],["REVIEW","PASS","Now PASS"],["PASS","ERROR","Now ERROR"],["ERROR","FAIL","New failure"],["FAIL","FAIL","Unchanged"]]) {
  test(`${old} to ${next}: ${expected}`,async()=>{
    const result=await compare(review("a",rule(old)),review("b",rule(next)));
    assert.deepEqual(result.blockers,[]);assert.equal(result.rows[0].change,expected);
  });
}
test("changed actual values and reasons are not hidden by unchanged decision",async()=>{
  const result=await compare(review("a"),review("b",rule("PASS","ABSENCE_PERMITTED",null)));
  assert.equal(result.rows[0].change,"Changed result");
});
for(const kind of ["same-candidate","project","track","profile","profile-version","no-evaluation","no-material","policy","bytes","wrong-commit","wrong-evaluation","wrong-material","wrong-profile-binding","wrong-material-track","wrong-status","duplicate-rule","missing-rule","expected"]) {
  test(`${kind} blocks like-for-like conclusions`,async()=>{
    const a=review("a"),b=review("b");
    if(kind==="same-candidate")b.candidate.candidate_id="a";
    if(kind==="project")b.candidate.project_id="other";
    if(kind==="track")b.candidate.release_track="release";
    if(kind==="profile")b.candidate.project_profile_id="other";
    if(kind==="profile-version")b.candidate.project_profile_version=2;
    if(kind==="no-evaluation")b.policy_evaluation=null;
    if(kind==="no-material")b.policy_material=null;
    if(kind==="policy")b.policy_material.policy_fingerprint=b.policy_evaluation.policy_fingerprint="different";
    if(kind==="bytes")b.policy_material.artifact.sha256="different";
    if(kind==="wrong-commit")b.policy_evaluation.candidate_commit="wrong";
    if(kind==="wrong-evaluation")b.policy_evaluation.evaluation_id="wrong";
    if(kind==="wrong-material")b.policy_evaluation.policy_material_id="wrong";
    if(kind==="wrong-profile-binding")b.policy_evaluation.project_profile_version=2;
    if(kind==="wrong-material-track")b.policy_material.release_track="wrong";
    if(kind==="wrong-status")b.candidate.status="DRAFT";
    if(kind==="duplicate-rule")b.policy_evaluation.rule_results.push(rule());
    if(kind==="missing-rule")b.policy_evaluation.rule_results=[];
    if(kind==="expected")b.policy_evaluation.rule_results[0].expected=10;
    const result=await compare(a,b);assert.ok(result.blockers.length);assert.deepEqual(result.rows,[]);
  });
}
test("JSON object key order does not cause an apparent result change",async()=>{
  const a=review("a",rule("PASS","OK",{x:1,y:2})),b=review("b",rule("PASS","OK",{y:2,x:1}));
  assert.equal((await compare(a,b)).rows[0].change,"Unchanged");
});

const all=(node,tag)=>[...(node.tag===tag?[node]:[]),...node.children.flatMap(child=>all(child,tag))];
const find=(a,label)=>all(a.panel,"button").find(b=>b.textContent===label);
async function click(a,label){await find(a,label).listeners.click[0]();await flush();}
async function setup(current=review("current")) {
  const a=await harness();a.context.fixture=current;
  runInContext("session={csrf_token:'fixture',principal:{role:'producer'}};window.location.hash='#/decision?candidate_id=current';document.querySelector('#app').append(decisionComparisonPanel(fixture));",a.context);
  a.panel=all(a.root,"section").find(n=>n.attributes["aria-label"]==="Compare evaluations");
  a.picker=all(a.panel,"select")[0];return a;
}
async function choices(a,candidates=[review("baseline").candidate],more=false) {
  a.responses.push({status:200,body:{candidates,has_more:more,next_after_candidate_id:more?"cursor":null}});
  await click(a,more&&find(a,"Load more baseline choices")?"Load more baseline choices":find(a,"Load baseline choices")?"Load baseline choices":"Refresh baseline choices");
}
async function select(a,id="baseline"){a.picker.value=id;a.picker.listeners.change[0]();await flush();}
test("explicit selection, both refreshed via GET, missing evidence surfaced",async()=>{
  const current=review("current",rule("FAIL","EVIDENCE_MISSING",null));current.policy_evaluation.rule_results[0].evidence_ids=[];
  const a=await setup(current);await choices(a);assert.equal(find(a,"Compare with current").disabled,true);
  await select(a);a.responses.push({status:200,body:review("baseline")},{status:200,body:current});
  await click(a,"Compare with current");assert.match(a.panel.text,/1 new failures.*1 current missing-evidence rules \(1 newly missing\)/);
  assert.ok(a.requests.slice(1).every(r=>!r.options.method || r.options.method==="GET"));
  assert.ok(a.requests.at(-1).path.endsWith("/current/assurance-review"));
});
test("permitted absence is not counted as missing evidence",async()=>{
  const current=review("current",rule("PASS","ABSENCE_PERMITTED",null)),a=await setup(current);
  await choices(a);await select(a);a.responses.push({status:200,body:review("baseline")},{status:200,body:current});await click(a,"Compare with current");
  assert.match(a.panel.text,/0 current missing-evidence rules/);
});
test("candidate paging is explicit, filters unevaluated/cross-project/self and deduplicates",async()=>{
  const a=await setup();await choices(a,[review("baseline").candidate,review("current").candidate,{...review("draft").candidate,evaluation_id:null},{...review("foreign").candidate,project_id:"other"}],true);
  assert.match(a.panel.text,/1 evaluated baseline/);assert.equal(a.picker.value,"");
  a.responses.push({status:200,body:{candidates:[review("baseline").candidate,review("second").candidate],has_more:false}});
  await click(a,"Load more baseline choices");assert.match(a.requests.at(-1).path,/after_candidate_id=cursor/);assert.equal(all(a.picker,"option").length,3);
});
for(const kind of ["session","route","selection"]) test(`late ${kind} change discards comparison`,async()=>{
  const a=await setup();await choices(a);await select(a);
  a.responses.push(()=>{if(kind==="session")runInContext("session=null",a.context);if(kind==="route")runInContext("window.location.hash='#/overview'",a.context);if(kind==="selection"){a.picker.value="";a.picker.listeners.change[0]();}return {status:200,body:review("baseline")};},{status:200,body:review("current")});
  await click(a,"Compare with current");assert.doesNotMatch(a.panel.text,/COMPARABLE ·/);
});
for(const code of [403,404,500]) test(`${code} failure removes old results and permits retry`,async()=>{
  const a=await setup();await choices(a);await select(a);
  a.responses.push({status:200,body:review("baseline")},{status:200,body:review("current")});await click(a,"Compare with current");assert.match(a.panel.text,/COMPARABLE ·/);
  a.responses.push({status:code},{status:200,body:review("current")});await click(a,"Compare with current");
  assert.doesNotMatch(a.panel.text,/COMPARABLE ·/);assert.match(a.panel.text,/Comparison unavailable/);assert.equal(find(a,"Compare with current").disabled,false);
});
test("double click loads one pair and wrong identity cannot render",async()=>{
  const a=await setup();await choices(a);await select(a);
  a.responses.push({status:200,body:review("wrong")},{status:200,body:review("current")});
  const handler=find(a,"Compare with current").listeners.click[0];await Promise.all([handler(),handler()]);
  assert.equal(a.requests.length,4);assert.match(a.panel.text,/Comparison unavailable/);
});
test("changed policy renders blockers without a changes table",async()=>{
  const a=await setup();await choices(a);await select(a);const baseline=review("baseline");baseline.policy_material.artifact.sha256="different";
  a.responses.push({status:200,body:baseline},{status:200,body:review("current")});await click(a,"Compare with current");
  assert.match(a.panel.text,/NOT COMPARABLE/);assert.equal(all(a.panel,"table").length,0);
});
