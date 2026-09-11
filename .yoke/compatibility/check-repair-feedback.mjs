import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {runQualityRepairLoop} from '../tooling/yoke/dist/quality/loop.js';
import {makeRunner} from '../tooling/yoke/dist/loop/runner.js';
import {readFileSync} from 'node:fs';
const blockers=[{severity:'blocking',message:'Fix incorrect output dimensions'},{severity:'blocking',message:'Validate widget values'}];
const warning={severity:'warning',message:'Optional wording'};
const rejected={kind:'rejected',verdict:{approved:false,summary:'Two blockers',findings:[...blockers,warning]}};
let reviews=0,gates=0,repairs=0;
const result=runQualityRepairLoop({
 review:()=>++reviews===1?rejected:{kind:'approved',verdict:{approved:true,summary:'Both fixed',findings:[]}},
 repair:request=>{repairs++;assert.deepEqual(request.finding,blockers[0]);assert.deepEqual(request.findings,blockers);return {kind:'repaired'};},
 rerunGates:()=>{gates++;return {kind:'passed'};},
});
assert.equal(result.kind,'approved');assert.equal(reviews,2);assert.equal(gates,1);assert.equal(repairs,1);
const failed=runQualityRepairLoop({review:()=>rejected,repair:()=>({kind:'repaired'}),rerunGates:()=>({kind:'failed',stage:'verify',summary:'Regression'})});
assert.equal(failed.kind,'blocked');assert.equal(failed.reason,'gate-failed');
const refused=runQualityRepairLoop({review:()=>rejected,repair:()=>({kind:'blocked',summary:'Could not repair'}),rerunGates:()=>{throw Error('Gate must not run');}});
assert.equal(refused.kind,'blocked');assert.equal(refused.reason,'repair-failed');
const exhausted=runQualityRepairLoop({review:()=>rejected,repair:()=>{throw Error('Budget must prevent repair');},rerunGates:()=>{throw Error('Gate must not run');},limits:{maxRounds:0}});
assert.equal(exhausted.kind,'blocked');
// Exercise the actual provider prompt builder used by the plain-review callback.
// The optional quality-critic repairPrompt is a different, upstream single-gap path.
const root=fileURLToPath(new URL('../../',import.meta.url)).replaceAll('\\','/').replace(/\/$/,'');
const command=readFileSync(root+'/.yoke/tooling/yoke/dist/loop/run-command.js','utf8');
assert.ok(command.includes('repair: (context, request) => runner({ ...context, feedback: JSON.stringify(request) })'));
let providerInput,secondReview=false;
const runner=makeRunner('codex',0,{execCapture:inv=>{providerInput=inv.input;return '';}});
const promptResult=runQualityRepairLoop({
 review:()=>secondReview?{kind:'approved',verdict:{approved:true,summary:'Reviewed',findings:[]}}:rejected,
 repair:request=>{secondReview=true;const r=runner({targetDir:root,story:{id:'feedback-prompt-probe',title:'Verify repair feedback',acceptance:[],needs:[],passes:false},feedback:JSON.stringify(request)});return {kind:r.success?'repaired':'blocked'};},
 rerunGates:()=>({kind:'passed'}),
});
assert.equal(promptResult.kind,'approved');
for(const finding of blockers)assert.ok(providerInput.includes(finding.message));
assert.ok(providerInput.includes('"findings":['));
const longBlockers=[{severity:'blocking',message:'Detailed first blocker',evidence:['x'.repeat(9000)]},{severity:'blocking',message:'REQUIRED-TARGET-SLOT-CHECK'}];
secondReview=false;
const longResult=runQualityRepairLoop({
 review:()=>secondReview?{kind:'approved',verdict:{approved:true,summary:'Reviewed',findings:[]}}:{kind:'rejected',verdict:{approved:false,summary:'Long review',findings:longBlockers}},
 repair:request=>{secondReview=true;const r=runner({targetDir:root,story:{id:'long-feedback-probe',title:'Verify long review feedback',acceptance:[],needs:[],passes:false},feedback:JSON.stringify(request)});return {kind:r.success?'repaired':'blocked'};},
 rerunGates:()=>({kind:'passed'}),
});
assert.equal(longResult.kind,'approved');
assert.ok(providerInput.includes('REQUIRED-TARGET-SLOT-CHECK'),'The final actionable blocker must survive beyond 8,000 characters');
runner({targetDir:root,story:{id:'ordinary-feedback-probe',title:'Preserve ordinary diagnostic bound',acceptance:[],needs:[],passes:false},feedback:'x'.repeat(9000)+'ORDINARY-DIAGNOSTIC-TAIL'});
assert.ok(!providerInput.includes('ORDINARY-DIAGNOSTIC-TAIL'));
console.log('PASS: all actionable review blockers reach repair; fresh review, gates, failed-repair and repair-budget checks remain enforced.');
