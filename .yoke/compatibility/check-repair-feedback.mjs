import assert from 'node:assert/strict';
import {runQualityRepairLoop} from '../tooling/yoke/dist/quality/loop.js';
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
console.log('PASS: all actionable review blockers reach repair; fresh review, gates, failed-repair and repair-budget checks remain enforced.');
