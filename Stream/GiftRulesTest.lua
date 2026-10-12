local R=... or dofile(THEME:GetCurrentThemeDirectory()..'BGAnimations/ScreenGameplay overlay/GiftRules.lua')
local checks=0
local function eq(a,b) assert(a==b,tostring(a)..' ~= '..tostring(b)) checks=checks+1 end
local config={tempo_limit_percent=.15,tempo_stored_limit_percent=.5,tempo_decay_measures=4,lock_min_measures=4,tempo_notice_seconds=4}
local function fresh() return R.new(config,200,{{0,4,4}},function() return 100 end) end
local function gift(id,kind,delta) return {event_id=id,sender='A',kind=kind,bpm_delta=delta,measures=4} end
local t=fresh()
eq(t:submit(gift('a','tempo',20),0),true)
t:step(.99,0) eq(t.offset,0)
t:step(1,.1) eq(t.offset,20) eq(t:bpm(100),115)
t:step(16,.2) eq(t.offset,20)
t:step(17,.3) eq(t.offset,19) eq(t:bpm(100),115)
eq(t:submit(gift('b','tempo',-10),17.2),true)
t:step(18,.4) eq(t.offset,9) eq(t:bpm(100),109)
eq(t:submit(gift('too-much','tempo',100),18.2),false)
local locked=fresh()
eq(locked:submit(gift('speed','tempo',10),0),true)
eq(locked:submit(gift('lock','lock'),0),true)
locked:step(1,1) eq(locked:bpm(100),110)
eq(locked:submit(gift('held','tempo',-20),1.1),true)
eq(locked:submit(gift('next','lock'),1.1),true)
locked:step(2,2) eq(locked.offset,10) eq(locked.pendingDelta,-20)
locked:step(16,3) eq(locked.offset,10) eq(locked:bpm(100),110)
locked:step(17,4) eq(locked.offset,-10) eq(locked:bpm(100),90) eq(locked.lock.event_id,'next')
locked:step(33,5) eq(locked.lock,nil) eq(locked.offset,-10)
locked:step(49,6) eq(locked.offset,-9)
local sold=R.new(config,16,{{0,4,4}},function() return 100 end)
eq(sold:remainingLocks(0),0) eq(sold:submit(gift('sold','lock'),0),false)
local feed=fresh()
feed:submit(gift('one','tempo',1),0) feed:submit(gift('two','tempo',1),0)
feed:step(1,1) eq(#feed.feed,1) eq(feed.feed[1].count,2)
feed:step(2,6) eq(#feed.feed,0)
eq(fresh().offset,0)
eq(R.measure(20,{{0,4,4},{16,3,4}}),4+4/3)
eq(R.beat(5,{{0,4,4},{16,3,4}}),19)
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
