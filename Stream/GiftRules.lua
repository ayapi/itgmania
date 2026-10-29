-- Version 5 trial / community rescue rules; pure Lua.
local R={}
local function clamp(v,a,b) return math.max(a,math.min(b,v)) end
function R.measure(beat,signatures)
 local result,last,size=0,0,4
 for _,sig in ipairs(signatures or {{0,4,4}}) do
  if sig[1]>beat then break end
  result=result+(sig[1]-last)/size
  last=sig[1] size=sig[2]*4/sig[3]
 end
 return result+(beat-last)/size
end
function R.beat(measure,signatures)
 local result,last,size=0,0,4
 for _,sig in ipairs(signatures or {{0,4,4}}) do
  local nextMeasure=result+(sig[1]-last)/size
  if nextMeasure>measure then break end
  result=nextMeasure last=sig[1] size=sig[2]*4/sig[3]
 end
 return last+(measure-result)*size
end
function R.rank(viewers)
 return viewers<50 and 1 or viewers<150 and 2 or viewers<350 and 3 or 4
end
function R.new(config,lastBeat,signatures,baseAt,carry,viewers,random)
 carry=carry or {} local rank=R.rank(viewers or 0)
 local t={config=config,lastBeat=lastBeat,signatures=signatures,baseAt=baseAt,rank=rank,
  viewers=viewers or 0,requiredUnits=({1,1,2,4})[rank],offset=0,pendingDelta=0,
  actions=carry.actions or {},locks={},lock=nil,trial=nil,feed={},appliedThisStep={},changes={},events=carry.events or {},
  completedLocks={},metrics={cap_seconds=0,trials=0,resolved=0,heart_taps_tiktok=0,heart_taps_youtube=0,
   rescue_gifts=0,gift_points=0,trial_gifts=0,lock_gifts=0},results={},lastBeatUpdated=-1,
  trialUnits=carry.trialUnits or {},lockUnits=carry.lockUnits or {},strongQueue=carry.strongQueue or {},
  rescueBank=carry.rescueBank or 0,bankEvents=carry.bankEvents or {},multiplier=carry.multiplier or 1,
  tiktokTotal=nil,tiktokStream=nil,locksUsed=0,restUntil=0,autoDone=0,autoTargets={},
  announcement=nil,deferredAuto=false,announcementSerial=0,attackAnnouncements=0,costChangedBeat=nil}
 setmetatable(t,{__index=R})
 -- A new song resets escalating attack prices; all unspent contributions survive.
 for _,g in ipairs(t.strongQueue) do for _,c in ipairs(g.tokens or {}) do t.trialUnits[#t.trialUnits+1]=c end end
 t.strongQueue={}
 t.locks=carry.locks or {}
 for _,g in ipairs(t.locks) do g.waiting=true end
 for _,c in ipairs(t.actions) do c.applyBeat=0 end
 local eligible={} local total=R.measure(lastBeat,signatures)
 for m=math.ceil(config.trial_intro_measures/8)*8,math.floor((total-config.trial_tail_measures)/8)*8,8 do eligible[#eligible+1]=m end
 random=random or math.random
 -- ITGmania replaces math.random and rejects equal two-argument bounds.
 local function choose(lo,hi) if lo==hi then return lo end return random(lo,hi) end
 if #eligible>0 then
  local first=choose(1,#eligible) t.autoTargets[1]=eligible[first]
  if first<#eligible and random()<config.trial_second_probability then t.autoTargets[2]=eligible[choose(first+1,#eligible)] end
 end
 t.autoUnavailable=#eligible==0
 return t
end
function R:event(id,state,reason,lockId)
 if not id then return end
 local value={state=state,reason=reason or '',lock_event_id=lockId}
 self.events[id]=value self.changes[id]=value
end
function R:limit(base) return math.floor(base*self.config.tempo_limit_percent+0.000001) end
function R:storedLimit(base) return self:limit(base) end
function R:applied(base) return clamp(self.offset,0,self:limit(base)) end
function R:bpm(base) return base+self:applied(base) end
function R:remainingLocks(beat)
 local m=R.measure(beat,self.signatures)
 local available=R.measure(self.lastBeat,self.signatures)-m
 if self.lock then available=available-math.max(0,self.lock.endMeasure-m) end
 return math.max(0,math.min(self.config.lock_max_per_song-self.locksUsed-#self.locks,math.floor((available+0.000001)/self.config.lock_min_measures)))
end
local function displayName(tokens)
 local names,seen={},{}
 for _,c in ipairs(tokens) do if not seen[c.sender] then names[#names+1]=c.sender seen[c.sender]=true end end
 if #names<=2 then return table.concat(names,'・') end
 return names[#names]..'＋ほか'..(#names-1)..'人'
end
function R:attackCost() return self.requiredUnits*2^self.attackAnnouncements end
function R:contributionCost() return self:attackCost() end
function R:group(units,required)
 local tokens={}
 for i=1,(required or self.requiredUnits) do tokens[i]=table.remove(units,1) end
 return {tokens=tokens,sender=displayName(tokens),event_id=tokens[#tokens].event_id,measures=self.config.lock_min_measures}
end
function R:tokenEvents(group,state,reason)
 for _,c in ipairs(group.tokens or {}) do self:event(c.event_id,state,reason) end
end
function R:submit(command,beat)
 if command.kind=='tempo' then return false,'Version 5 uses trial/rescue instead of tempo' end
 if command.kind~='trial' and command.kind~='rescue' and command.kind~='lock' and command.kind~='hearts' then return false,'Unknown command' end
 command.applyBeat=math.floor(beat+0.000001)+1
 self.actions[#self.actions+1]=command
 self:event(command.event_id,'queued','Applies on next beat') return true
end
function R:finishTrial(now,resolved,why)
 local t=self.trial if not t then return end
 local duration=math.max(0,now-t.startedAt)
 self.results[#self.results+1]={kind=t.kind,required=t.required,heart_points=t.heartPoints,
  gift_points=t.giftPoints,duration_seconds=duration,resolved=resolved,reason=why,sender=t.sender}
 self.metrics.resolved=self.metrics.resolved+(resolved and 1 or 0)
 if not resolved then self.multiplier=clamp(self.multiplier*0.8,0.5,2)
 elseif duration<self.config.trial_fast_seconds then self.multiplier=clamp(self.multiplier*1.2,0.5,2) end
 if t.group then self:tokenEvents(t.group,'completed',resolved and 'Trial rescued' or 'Trial reached song end') end
 local beat=self.lastBeatUpdated
 self.resolution={resolved=resolved,at=now,beat=beat,end_beat=beat+clamp(self.config.trial_clear_beats or 2,1,2),reason=why,
  required_points=t.required,points=t.progress,kind=t.kind,rise=t.rise}
 self.trial=nil self.offset=0
 self.restUntil=(math.floor(R.measure(self.lastBeatUpdated,self.signatures)/8)+2)*8
end
function R:rescue(points,command,now)
 if command then
  local count=command.gift_count or 1 local unit=points/count
  local last
  for i=#self.feed,1,-1 do
   local row=self.feed[i]
   if row.sender==command.sender and row.unit_points==unit and now-row.last_at<1.5 then last=row break end
  end
  if last then
   last.points=last.points+points last.count=last.count+count last.last_at=now
  else self.feed[#self.feed+1]={event_id=command.event_id,sender=command.sender,points=points,unit_points=unit,count=count,last_at=now} end
  while #self.feed>8 do table.remove(self.feed,1) end
 end
 if not self.trial then
  self.rescueBank=self.rescueBank+points
  if command then self.bankEvents[#self.bankEvents+1]=command self:event(command.event_id,'carried','Rescue points saved for next trial') end
  return
 end
 local t=self.trial local used=math.min(points,math.max(0,t.required-t.progress))
 t.giftPoints=t.giftPoints+used t.progress=t.progress+used
 if points>used then self.rescueBank=self.rescueBank+points-used end
 self.offset=math.max(0,t.rise-math.floor(t.progress*t.rise/t.required+0.000001))
 if command then
  self:event(command.event_id,'applied','Gift rescue points applied')

 end
 if self.offset==0 then self:finishTrial(now,true,'rescue') end
end
function R:startTrial(kind,group,beat,now)
 local rise=kind=='strong' and self:limit(self.baseAt(beat)) or math.min(self.config.trial_bpm_delta,self:limit(self.baseAt(beat)))
 if rise<1 then return false end
 local base=({40,160,320,640})[self.rank]*(kind=='strong' and 1.5 or 1)
 self.trial={kind=kind,sender=group and group.sender or '自動試練',group=group,rise=rise,
  required=math.max(1,math.floor(base*self.multiplier+0.5)),progress=0,heartPoints=0,giftPoints=0,
  heartPending=0,tapRemainder=0,heartMeasure=-1,heartSpent=0,startedAt=now,startMeasure=R.measure(beat,self.signatures),
  heartBaselineReady=kind~="strong",heartsAfter=R.measure(beat,self.signatures)+(kind=='strong' and self.config.strong_heart_disabled_measures or 0)}
 self.offset=rise self.metrics.trials=self.metrics.trials+1
 if group then self:tokenEvents(group,'active','Strong trial started') end
 -- The last observed TikTok cumulative total is the new baseline.
 if self.rescueBank>0 then
  local bank=self.rescueBank self.rescueBank=0
  for _,c in ipairs(self.bankEvents) do self:event(c.event_id,'applied','Banked points applied to trial') end
  self.bankEvents={} self:rescue(bank,nil,now)
 end
 return true
end
function R:noticeMeasures() return math.max(1,math.floor(self.config.trial_notice_measures or 4)) end
function R:announce(kind,group,startMeasure,beat)
 self.announcementSerial=self.announcementSerial+1
 self.announcement={kind=kind,group=group,sender=group and group.sender or nil,
  id=self.announcementSerial,announcedBeat=beat,startMeasure=startMeasure,
  startBeat=R.beat(startMeasure,self.signatures)}
 if group then
  if not group.announced then
   group.announced=true self.attackAnnouncements=self.attackAnnouncements+1 self.costChangedBeat=beat
  end
  self:tokenEvents(group,'reserved','Strong trial countdown started')
 end
end
function R:cancelAnnouncement()
 local a=self.announcement if not a then return end
 if a.group then table.insert(self.strongQueue,1,a.group)
 else self.deferredAuto=true end
 self.announcement=nil
end
function R:hearts(c,beat)
 local count=0
 if c.platform=='tiktok' then
  if self.tiktokTotal and not c.reset and (not c.stream_id or c.stream_id==self.tiktokStream) then
   local delta=c.total-self.tiktokTotal
   if delta>=0 and delta<=self.config.tiktok_max_delta then count=delta end
  end
  self.tiktokTotal=c.total self.tiktokStream=c.stream_id or self.tiktokStream
 else count=c.count end
 self.metrics['received_hearts_'..c.platform]=(self.metrics['received_hearts_'..c.platform] or 0)+count
 local t=self.trial local m=R.measure(beat,self.signatures)
 if not t or m<t.heartsAfter then return end
 if c.platform=="tiktok" and not t.heartBaselineReady then t.heartBaselineReady=true count=0 end
 self.metrics['heart_taps_'..c.platform]=self.metrics['heart_taps_'..c.platform]+count
 t.tapRemainder=t.tapRemainder+count
 local points=math.floor(t.tapRemainder/self.config.heart_taps_per_point)
 t.tapRemainder=t.tapRemainder-points*self.config.heart_taps_per_point
 t.heartPending=t.heartPending+points
end
function R:startLock(group,beat,now)
 self:cancelAnnouncement()
 if self.trial then self:finishTrial(now,true,'lock') end
 self.offset=0 self.locksUsed=self.locksUsed+1
 self.lock={event_id=group.event_id,sender=group.sender,tokens=group.tokens,bpm=self.baseAt(beat),
  startMeasure=R.measure(beat,self.signatures),measures=self.config.lock_min_measures}
 self.lock.endMeasure=self.lock.startMeasure+self.lock.measures self.lock.endBeat=R.beat(self.lock.endMeasure,self.signatures)
 self:tokenEvents(group,'active','Original BPM locked')
end
function R:process(c,beat,now)
 if c.kind=='hearts' then self:hearts(c,beat) self:event(c.event_id,'applied')
 elseif c.kind=='rescue' then
  self.metrics.rescue_gifts=self.metrics.rescue_gifts+1 self.metrics.gift_points=self.metrics.gift_points+c.points
  self:rescue(c.points,c,now)
 else
  local units=c.kind=='trial' and self.trialUnits or self.lockUnits
  for i=1,c.count do units[#units+1]=c end
  self.metrics[c.kind..'_gifts']=self.metrics[c.kind..'_gifts']+c.count
  self:event(c.event_id,'contributing','Waiting for enough gift units')
 end
end
function R:atBeat(beat,now)
 local m=R.measure(beat,self.signatures) self.lastBeatUpdated=beat
 if self.lock and beat>=self.lock.endBeat-0.000001 then
  self:tokenEvents(self.lock,'completed','Lock ended')
  self.completedLocks[#self.completedLocks+1]=self.lock.event_id self.lock=nil
 end
 while self.actions[1] and self.actions[1].applyBeat<=beat do self:process(table.remove(self.actions,1),beat,now) end
 if #self.strongQueue==0 and #self.trialUnits>=self:contributionCost() then
  local g=self:group(self.trialUnits,self:contributionCost()) self.strongQueue[#self.strongQueue+1]=g self:tokenEvents(g,'reserved','Strong trial reserved')
 end
 while #self.lockUnits>=self.requiredUnits and self:remainingLocks(beat)>0 do
  local g=self:group(self.lockUnits) self.locks[#self.locks+1]=g
  self:tokenEvents(g,'reserved','Shield waiting for a trial')
 end
 -- New shields interrupt an active warning/trial, but never chain during protection.
 if not self.lock and (self.trial or self.announcement) then
  for i,g in ipairs(self.locks) do if not g.waiting then self:startLock(table.remove(self.locks,i),beat,now) break end end
 end
 for _,g in ipairs(self.locks) do g.waiting=true end
 local t=self.trial
 if t then
  if m>=t.heartsAfter then
   if t.heartMeasure~=math.floor(m+0.000001) then t.heartMeasure=math.floor(m+0.000001) t.heartSpent=0 end
   local unit=t.required/t.rise
   local use=math.min(t.heartPending,math.max(0,unit-t.heartSpent),t.required-t.progress)
   t.heartPending=t.heartPending-use t.heartSpent=t.heartSpent+use t.progress=t.progress+use t.heartPoints=t.heartPoints+use
   self.offset=math.max(0,t.rise-math.floor(t.progress*t.rise/t.required+0.000001))
   if self.offset==0 then self:finishTrial(now,true,'hearts') end
  end
 end
 local a=self.announcement
 if a and not self.lock and beat>=a.startBeat-0.000001 then
  self.announcement=nil
  if a.kind=='normal' then self.autoDone=self.autoDone+1 end
  self:startTrial(a.kind,a.group,beat,now)
  if self.trial then self.trial.startBeat=a.startBeat end
  if #self.locks>0 then self:startLock(table.remove(self.locks,1),beat,now) end
 end
 local notice=self:noticeMeasures()
 local total=R.measure(self.lastBeat,self.signatures)
 local canAnnounce=not self.lock and not self.trial and not self.announcement
  and m>=math.max(0,self.config.trial_intro_measures-notice)
  and total-m>=self.config.trial_tail_measures+notice-0.000001
 if canAnnounce and #self.strongQueue>0 then
  self:announce('strong',table.remove(self.strongQueue,1),m+notice,beat)
 elseif canAnnounce and self.deferredAuto then
  self.deferredAuto=false self:announce('normal',nil,m+notice,beat)
 elseif canAnnounce and self.autoTargets[1] then
  -- Auto starts remain on eight-measure boundaries. If blocked, move the
  -- planned start forward instead of shortening the four-measure warning.
  local target=math.max(self.autoTargets[1],self.restUntil,math.ceil((m+notice-0.000001)/8)*8)
  if m>=target-notice-0.000001 and target<=total-self.config.trial_tail_measures+0.000001 then
   table.remove(self.autoTargets,1) self:announce('normal',nil,target,beat)
  end
 end
 self.offset=self:applied(self.baseAt(beat))
end
function R:step(beat,now)
 self.now=now self.appliedThisStep={}
 if beat<0 then return end
 for b=math.max(0,self.lastBeatUpdated+1),math.floor(beat+0.000001) do self:atBeat(b,now) end
 for i=#self.feed,1,-1 do if now-self.feed[i].last_at>self.config.rescue_notice_seconds then table.remove(self.feed,i) end end
end
function R:finish(now)
 self.now=now
 if self.trial then self:finishTrial(now,false,'song ended') end
 self:cancelAnnouncement()
 for _,c in ipairs(self.actions) do self:process(c,self.lastBeatUpdated,now) end self.actions={}
 if self.lock then self:tokenEvents(self.lock,'completed','Song ended') self.lock=nil end
 for _,units in ipairs({self.trialUnits,self.lockUnits,self.bankEvents}) do for _,c in ipairs(units) do self:event(c.event_id,'carried','Carried to next song') end end
 for _,g in ipairs(self.strongQueue) do self:tokenEvents(g,'carried','Strong trial carried to next song') end
 for _,g in ipairs(self.locks) do self:tokenEvents(g,'carried','Shield carried to next song') end
end
function R:export()
 local events={} local function keep(c) if self.events[c.event_id] then events[c.event_id]=self.events[c.event_id] end end
 for _,units in ipairs({self.trialUnits,self.lockUnits,self.bankEvents,self.actions}) do for _,c in ipairs(units) do keep(c) end end
 for _,g in ipairs(self.strongQueue) do for _,c in ipairs(g.tokens) do keep(c) end end
 for _,g in ipairs(self.locks) do for _,c in ipairs(g.tokens or {}) do keep(c) end end
 local queue={} for _,g in ipairs(self.strongQueue) do queue[#queue+1]=g end
 if self.announcement and self.announcement.group then
  table.insert(queue,1,self.announcement.group)
  for _,c in ipairs(self.announcement.group.tokens) do keep(c) end
 end
 return {actions=self.actions,locks=self.locks,trialUnits=self.trialUnits,lockUnits=self.lockUnits,strongQueue=queue,
  rescueBank=self.rescueBank,bankEvents=self.bankEvents,multiplier=self.multiplier,events=events}
end
function R:status(beat)
 local t=self.trial
 local a=self.announcement local m=R.measure(beat,self.signatures)
 local remaining=a and math.max(0,a.startMeasure-m) or 0
 local final=a and m>=a.startMeasure-1
 local forecast=a and {id=a.id,kind=a.kind,sender=a.sender,start_beat=a.startBeat,
  rise=a.kind=='strong' and self:limit(self.baseAt(a.startBeat)) or math.min(self.config.trial_bpm_delta,self:limit(self.baseAt(a.startBeat))),
  final_measure_beat=R.beat(a.startMeasure-1,self.signatures),
  remaining_measures=math.ceil(remaining-0.000001),countdown=final and math.max(1,math.ceil(a.startBeat-beat-0.000001)) or nil} or nil
 if forecast then
  forecast.measure_boundaries={}
  for i=self:noticeMeasures(),0,-1 do forecast.measure_boundaries[#forecast.measure_boundaries+1]=R.beat(a.startMeasure-i,self.signatures) end
 end
 local resolution=self.resolution and self.resolution.resolved and beat<self.resolution.end_beat and self.resolution or nil
 return {rank=self.rank,viewers=self.viewers,required_units=self.requiredUnits,attack_required_units=self:attackCost(),attack_contribution_required=self:contributionCost(),
  attack_announcements=self.attackAnnouncements,cost_changed_beat=self.costChangedBeat,
  shield_waiting=#self.locks,shield_waiting_sender=self.locks[1] and self.locks[1].sender or nil,trial=t and {
  kind=t.kind,sender=t.sender,rise=t.rise,start_beat=t.startBeat,required_points=t.required,points=t.progress,
  remaining_points=math.max(0,t.required-t.progress),heart_points=t.heartPoints,gift_points=t.giftPoints,
  heart_pending=t.heartPending,hearts_enabled=R.measure(beat,self.signatures)>=t.heartsAfter} or nil,
  announcement=forecast,next_trial_sender=self.strongQueue[1] and self.strongQueue[1].sender or nil,
  trial_units=#self.trialUnits,trial_reserved=#self.strongQueue+(a and a.kind=='strong' and 1 or 0),lock_units=#self.lockUnits,
  lock_remaining=self:remainingLocks(beat),locks_used=self.locksUsed,rescue_bank=self.rescueBank,
  rescue_feed=self.feed,trial_results=self.results,resolution=resolution,
  auto_trial_unavailable=self.autoUnavailable,auto_trials_planned=self.autoDone+#self.autoTargets+(a and a.kind=='normal' and 1 or 0)+(self.deferredAuto and 1 or 0),metrics=self.metrics}
end

-- Greedy, deterministic inventory. Original chart rows and earlier planned
-- gifts are considered together, so adjacent jumps cannot be introduced.
function R.notePlan(notes,lastBeat,isJudgable)
 local rows,holds,ordered={},{},{}
 for _,n in ipairs(notes) do
  if n[3]=='TapNoteType_Tap' or n[3]=='TapNoteType_Lift' or n[3]=='TapNoteType_HoldHead' then
   local row=math.floor(n[1]*48+0.5)
   if not rows[row] then rows[row]={} ordered[#ordered+1]=row end
   rows[row][n[2]]=true
   if n.length and n.length>0 then holds[#holds+1]=n end
  end
 end
 table.sort(ordered)
 local function feetAt(beat)
  local feet={} local row=rows[math.floor(beat*48+0.5)] or {}
  for col in pairs(row) do feet[col]=true end
  for _,n in ipairs(holds) do if beat>=n[1] and beat<=n[1]+n.length then feet[n[2]]=true end end
  local count=0 for _ in pairs(feet) do count=count+1 end
  return feet,count
 end
 local result={} local position=1 local previousGift
 for beat=0,lastBeat-0.5,0.5 do
  local row=math.floor(beat*48+0.5)
  while ordered[position] and ordered[position]<row do position=position+1 end
  local before=ordered[position-1] and ordered[position-1]/48
  local after=ordered[position] and ordered[position]/48
  local nextRow=after==beat and ordered[position+1] and ordered[position+1]/48 or after
  local distanceOK=(not before or beat-before>=0.5-0.000001) and (not nextRow or nextRow-beat>=0.5-0.000001)
  local occupied,count=feetAt(beat)
  if count<2 and distanceOK and (not previousGift or beat-previousGift>=0.5) and isJudgable(beat) then
   local jump=count==1
   local prev=before
   if previousGift and (not prev or previousGift>prev) then prev=previousGift end
   local _,prevFeet=feetAt(prev or -100)
   local _,nextFeet=feetAt(nextRow or lastBeat+100)
   if not jump or (prevFeet<2 and nextFeet<2) then
    local col=(#result%4)+1
    for i=0,3 do local candidate=(col+i-1)%4+1
     if not occupied[candidate] then col=candidate break end
    end
    result[#result+1]={beat=beat,column=col}
    rows[row]=rows[row] or {} rows[row][col]=true
    previousGift=beat
   end
  end
 end
 return result
end
return R
