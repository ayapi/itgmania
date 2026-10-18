const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync(require('path').join(__dirname,'overlay.html'),'utf8');
const code=html.slice(html.indexOf('function challengePresentation'),html.indexOf('let cueClock'));
const ctx={};vm.createContext(ctx);vm.runInContext(code,ctx);
const st={announcement:{kind:'strong',sender:'ギフターA＋ほか2人',start_beat:96,final_measure_beat:92,remaining_measures:4,measure_boundaries:[80,84,88,92,96]}};
for(const [beat,count] of [[80,4],[84,3],[88,2]]){
 const cue=ctx.challengePresentation(st,beat);assert.equal(cue.mode,'announcing');assert.equal(cue.phase,`開始まで${count}小節`);assert.equal(cue.sender,st.announcement.sender);
}
for(let b=92;b<96;b+=.125){const cue=ctx.challengePresentation(st,b);assert.equal(cue.mode,'counting');assert.equal(cue.title,String(Math.ceil(96-b)));}
st.resolution={resolved:true,beat:80,end_beat:82};
for(const b of [80,81,81.9]){const cue=ctx.challengePresentation(st,b);assert.equal(cue.mode,'clearing');assert.equal(cue.title,'CHALLENGE CLEAR!');assert.equal(cue.sender,'');}
assert.equal(ctx.challengePresentation(st,82).mode,'announcing');
assert.equal(ctx.challengePresentation({},100),null);
assert.equal(ctx.challengePresentation({trial:{kind:'normal',rise:10,hearts_enabled:true}},100).mode,'active');
const panel={hidden:false};ctx.document={getElementById:()=>panel};ctx.performance={now:()=>1000};
vm.runInContext(html.slice(html.indexOf('let cueClock'),html.indexOf('function drawChallenge')),ctx);
vm.runInContext('syncChallenge({protocol_version:5,ready:true,effective_bpm:150,song_beat:80},0)',ctx);
assert(vm.runInContext('cueClock!==null',ctx),'Legacy games retain browser challenge display');
vm.runInContext('syncChallenge({native_trial_panel:true},0)',ctx);
assert.equal(vm.runInContext('cueClock',ctx),null);
assert.equal(panel.hidden,true,'Native challenge HUD must suppress the duplicate browser panel');
console.log('PASS: measure countdown, locally interpolated beat numbers, two-beat clear, no clear sender, return to next notice');
