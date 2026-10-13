local R=... or dofile(THEME:GetCurrentThemeDirectory()..'BGAnimations/ScreenGameplay overlay/GiftRules.lua')
local checks=0
local function eq(a,b) assert(a==b,tostring(a)..' ~= '..tostring(b)) checks=checks+1 end
local config={tempo_limit_percent=.15,lock_min_measures=4,lock_max_per_song=2,
 trial_intro_measures=24,trial_tail_measures=16,trial_second_probability=0,
 trial_bpm_delta=10,trial_fast_seconds=20,strong_heart_disabled_measures=4,
 heart_taps_per_point=20,tiktok_max_delta=100000,rescue_notice_seconds=1.2}
local function random(a,b) return a or 1 end
local function fresh(carry,viewers,last) return R.new(config,last or 400,{{0,4,4}},function() return 108 end,carry,viewers or 100,random) end
local serial=0
local function gift(kind,value,sender)
 serial=serial+1 local c={event_id='test-'..serial,kind=kind,sender=sender or 'A',count=1}
 if kind=='rescue' then c.points=value elseif kind=='hearts' then c.platform='youtube' c.count=value else c.count=value or 1 end
 return c
end
for _,v in ipairs({0,49,50,149,150,349,350}) do eq(R.rank(v),v<50 and 1 or v<150 and 2 or v<350 and 3 or 4) end
local t=fresh() t:step(95,0) eq(t.offset,0) t:step(96,1) eq(t.offset,10) eq(t.trial.required,160)
t:step(112,10) eq(t.offset,10) -- no automatic decay
local c=gift('rescue',16) eq(t:submit(c,112.1),true) t:step(112.9,11) eq(t.offset,10) t:step(113,12) eq(t.offset,9)
t:submit(gift('rescue',1000),113) t:step(114,40) eq(t.offset,0) eq(t.metrics.resolved,1) eq(t.rescueBank,856)
eq(t:submit(gift('tempo',1),114),false)
local h=fresh() h:step(96,0) h:submit(gift('hearts',32000),96) h:step(97,1) eq(h.offset,9)
h:step(99,2) eq(h.offset,9) h:step(100,3) eq(h.offset,8) h:step(132,20) eq(h.offset,0)
local strong=fresh();strong:submit(gift('trial'),0);strong:step(95,1);eq(strong.offset,0);eq(#strong.strongQueue,1)
strong:step(96,2);eq(strong.trial.kind,'strong');eq(strong.offset,16);eq(strong.trial.required,240)
strong:submit(gift('hearts',99999),96);strong:step(97,3);eq(strong.offset,16)
strong:submit(gift('rescue',15),97);strong:step(98,4);eq(strong.offset,15) -- paid rescue works in blocked heart period
strong:submit(gift('lock'),98);strong:step(99,5);eq(strong.offset,0);eq(strong.lock.bpm,108);eq(strong.trial,nil)
strong:submit(gift('trial'),99);strong:step(100,6);eq(#strong.strongQueue,1)
strong:step(115,10);eq(strong.trial.kind,'strong');eq(strong.offset,16) -- no rest before reserved attack
local lock=fresh();lock:submit(gift('lock',3),0);lock:step(1,1);eq(lock.locksUsed,1);lock:step(17,5);eq(lock.locksUsed,2);lock:step(33,9);eq(lock.lock,nil);eq(lock:remainingLocks(33),0);eq(#lock.lockUnits,1)
lock:finish(10);local replay=fresh(lock:export());eq(replay.offset,0);replay:step(0,0);eq(replay.lock~=nil,true);eq(replay.locksUsed,1)
local contribution=fresh(nil,350);contribution:submit(gift('trial',2,'A'),0);contribution:step(1,1);eq(#contribution.trialUnits,2)
contribution:submit(gift('trial',2,'B'),1);contribution:step(2,2);eq(#contribution.strongQueue,1);eq(contribution.strongQueue[1].sender,'A・B')
local late=fresh(nil,100,80);late:submit(gift('trial'),70);late:step(71,1);eq(late.offset,0);late:finish(2)
local carry=fresh(late:export());eq(#carry.strongQueue,1);carry:step(96,1);eq(carry.trial.kind,'strong')
local bank=fresh();bank:submit(gift('rescue',40),0);bank:step(1,1);eq(bank.rescueBank,40);bank:step(96,5);eq(bank.offset,8);eq(bank.rescueBank,0)
local tt=fresh();tt:submit({kind='hearts',event_id='tt1',platform='tiktok',total=1000},0);tt:step(1,0)
tt:step(96,1);tt:submit({kind='hearts',event_id='tt2',platform='tiktok',total=1320},96);tt:step(97,2);eq(tt.offset,9)
tt:submit({kind='hearts',event_id='tt3',platform='tiktok',total=10},97);tt:step(98,3);eq(tt.metrics.heart_taps_tiktok,320)
tt:submit({kind='hearts',event_id='tt4',platform='tiktok',total=10000000},98);tt:step(99,4);eq(tt.metrics.heart_taps_tiktok,320)
local fail=fresh();fail:step(96,1);fail:finish(100);eq(fail.multiplier,.8);eq(fail.results[1].resolved,false)
local fast=fresh();fast:step(96,0);fast:submit(gift('rescue',160),96);fast:step(97,1);eq(fast.multiplier,1.2)
eq(fresh(nil,100,80).autoUnavailable,true)
eq(R.measure(20,{{0,4,4},{16,3,4}}),4+4/3);eq(R.beat(5,{{0,4,4},{16,3,4}}),19)
local merged=fresh();merged:rescue(2,gift('rescue',2,'A'),0);merged:rescue(3,gift('rescue',3,'B'),.1);merged:rescue(2,gift('rescue',2,'A'),.2)
eq(#merged.feed,2);eq(merged.feed[1].count,2);eq(merged.rescueBank,7)
-- Reproduce the penultimate draw and a single remaining second-trial slot.
local c2={} for k,v in pairs(config) do c2[k]=v end c2.trial_second_probability=1
local function penultimate(a,b) if not a then return 0 end assert(a<b) return b-1 end
local edge=R.new(c2,377.5,{{0,4,4}},function() return 90 end,nil,100,penultimate)
eq(#edge.autoTargets,2);eq(edge.autoTargets[1],64);eq(edge.autoTargets[2],72)
-- Use the real engine RNG, including one-slot and two-slot ranges.
for _,last in ipairs({160,192,377.5,400}) do
 for i=1,100 do
  local r=R.new(c2,last,{{0,4,4}},function() return 90 end)
  assert(#r.autoTargets>=1);checks=checks+1
  for j,m in ipairs(r.autoTargets) do
   assert(m>=24 and m<=last/4-16 and m%8==0);checks=checks+1
   if j>1 then assert(m>r.autoTargets[j-1]);checks=checks+1 end
  end
 end
end
local function n(beat,col,length) return {beat,col,length and 'TapNoteType_HoldHead' or 'TapNoteType_Tap',length=length} end
local plan=R.notePlan({n(0,1,4),n(2,2),n(4,1),n(6,1),n(6,2)},8,function() return true end)
local occupied={};for _,note in ipairs({n(0,1,4),n(2,2),n(4,1),n(6,1),n(6,2)}) do
 local key=note[1] occupied[key]=occupied[key] or {} occupied[key][note[2]]=true
end
local lastGift
for _,note in ipairs(plan) do
 eq(note.beat*2,math.floor(note.beat*2))
 if lastGift then assert(note.beat-lastGift>=.5) checks=checks+1 end
 lastGift=note.beat
 local row=occupied[note.beat] or {} assert(not row[note.column]) checks=checks+1
 row[note.column]=true occupied[note.beat]=row
end
local previousFeet=0
for b=0,7.5,.5 do
 local row=occupied[b] or {} local feet={}
 for c in pairs(row) do feet[c]=true end
 if b<=4 then feet[1]=true end
 local count=0 for _ in pairs(feet) do count=count+1 end
 assert(count<=2) checks=checks+1
 if next(row) then assert(not(count==2 and previousFeet==2)) checks=checks+1 previousFeet=count end
end
return checks
