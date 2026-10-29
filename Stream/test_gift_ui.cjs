const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const html=fs.readFileSync(path.join(__dirname,'overlay.html'),'utf8');
class Element {
 constructor(){this.children=[];this.style={};this.dataset={};this.hidden=false;this.textContent='';}
 append(...items){this.children.push(...items)} replaceChildren(...items){this.children=items}
 remove(){} animate(){}
}
const elements=new Map(),get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id)};
const ctx={document:{getElementById:get,createElement:()=>new Element()},syncPulse(){},syncChallenge(){},
 drawChallenge(){throw Error('native meter should suppress browser meter')},number:String,rows:new Map(),session:null,panel:get('panel'),list:get('effects')};
vm.createContext(ctx);vm.runInContext(html.slice(html.indexOf('function render(status'),html.indexOf('function animateChallenge')),ctx);
const menu=JSON.parse(fs.readFileSync(path.join(__dirname,'gift-map.json')));
const gifts=Object.entries(menu).flatMap(([platform,g])=>Object.values(g).map(v=>({...v,platform})));
const status={protocol_version:5,ready:true,connected:true,native_trial_panel:true,session:'a',song_beat:100,
 song_title:'<b>曲名</b>',gift_menu:gifts,bpm_offset_limit:21,trial_state:{required_units:1,attack_required_units:1,lock_remaining:2}};
ctx.render(status);
assert.equal(get('title').textContent,'♪ <b>曲名</b>');
assert.equal(get('attack-gifts').children.length,2);assert.equal(get('shield-gifts').children.length,2);
assert(get('rescue-menu').hidden);assert(get('attack-contribution').hidden);assert(get('shield-contribution').hidden);
ctx.render({...status,trial_state:{required_units:2,attack_required_units:4,trial_units:1,lock_units:1,lock_remaining:0,
 shield_waiting:2,shield_waiting_sender:'<script>名前</script>',cost_changed_beat:99}});
assert.equal(get('attack-count').textContent,'1 / 4');assert(!get('attack-contribution').hidden);
assert.equal(get('shield-stock').textContent,'SOLD OUT');assert(!get('shield-waiting').hidden);
assert(get('shield-waiting').textContent.includes('<script>名前</script>'));assert(!get('cost-notice').hidden);
ctx.render({...status,trial_state:{required_units:1,attack_required_units:2,lock_remaining:1,cost_changed_beat:90,
 trial:{hearts_enabled:false,points:10,required_points:100,remaining_points:90},rescue_feed:[{event_id:'gift',sender:'名前',points:10,count:5}]}});
assert(!get('rescue-menu').hidden);assert(get('cost-notice').hidden);
assert.equal(get('effects').children[0].children[1].textContent,'+2pt ×5');
ctx.render({...status,ready:false,trial_state:{}});assert(get('panel').hidden);
assert(!html.includes('id="rank"'));assert(!html.includes('NOTE ATTACK'));
console.log('PASS: gift menus, waiting shields, escalating prices, rescue aggregation, native meter and literal names');
