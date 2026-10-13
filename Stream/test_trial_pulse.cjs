const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync(require('path').join(__dirname,'overlay.html'),'utf8');
const code=html.slice(html.indexOf('function trialPulseOpacity'),html.indexOf('function render(status'));
let now=0;const wash={style:{opacity:'0'}};
const ctx={document:{getElementById:()=>wash},performance:{now:()=>now},requestAnimationFrame:()=>{}};
vm.createContext(ctx);vm.runInContext(code,ctx);
const near=(a,b)=>assert(Math.abs(a-b)<1e-8,`${a} != ${b}`);
const active={protocol_version:5,ready:true,connected:true,effective_bpm:120,song_beat:0,trial_state:{trial:{}}};
ctx.syncPulse(active);ctx.animatePulse(0);near(+wash.style.opacity,.16);
ctx.animatePulse(250);near(+wash.style.opacity,.04);
ctx.animatePulse(500);near(+wash.style.opacity,.16);
// High BPM stays aligned to every second beat and caps pulse frequency.
ctx.syncPulse({...active,effective_bpm:240});ctx.animatePulse(250);near(+wash.style.opacity,.04);
ctx.syncPulse({...active,snapshot_age_seconds:.1},.05);ctx.animatePulse(0);near(+wash.style.opacity,ctx.trialPulseOpacity(.3,120));
for(const state of [{...active,ready:false},{...active,connected:false},{...active,trial_state:{}}]){ctx.syncPulse(state);near(+wash.style.opacity,0);}
ctx.syncPulse(active);ctx.animatePulse(1501);near(+wash.style.opacity,0);
for(const bpm of [90,140,161,180,210,240,360])for(let b=0;b<8;b+=.01){const alpha=ctx.trialPulseOpacity(b,bpm);assert(alpha>=.04-1e-10&&alpha<=.16+1e-10);assert(bpm/60/Math.max(1,Math.ceil(bpm/180))<=3);}
console.log('PASS: beat interpolation, speed changes, age compensation, pause/resolution/disconnect, stale timeout and opacity/frequency bounds');
