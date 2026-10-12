-- Version 3 gameplay rules. Pure Lua: no file I/O or game globals.
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
function R.new(config,lastBeat,signatures,baseAt)
 local t={config=config,lastBeat=lastBeat,signatures=signatures,baseAt=baseAt,
  offset=0,pendingDelta=0,held={},actions={},locks={},lock=nil,
  lastBeatUpdated=0,decayElapsed=0,feed={},appliedThisStep={},serial=0,lockReserved=0,events={},changes={},completedLocks={},
  metrics={tempo_gifts=0,lock_gifts=0,cap_seconds=0,max_overflow=0}}
 return setmetatable(t,{__index=R})
end
function R:event(id,state,reason,lockId)
 local value={state=state,reason=reason or '',lock_event_id=lockId}
 self.events[id]=value self.changes[id]=value
end
function R:limit(base) return math.floor(base*self.config.tempo_limit_percent+0.000001) end
function R:storedLimit(base) return math.floor(base*self.config.tempo_stored_limit_percent+0.000001) end
function R:applied(base) return clamp(self.offset,-self:limit(base),self:limit(base)) end
function R:bpm(base) return self.lock and self.lock.bpm or base+self:applied(base) end
function R:remainingLocks(beat)
 local start=math.floor(beat+0.000001)+1
 local measures=R.measure(self.lastBeat,self.signatures)-R.measure(start,self.signatures)-self.lockReserved
 return math.max(0,math.floor((measures+0.000001)/self.config.lock_min_measures))
end
function R:submit(command,beat)
 local base=self.baseAt(beat)
 if command.kind=='tempo' then
  local delta=command.bpm_delta
  local existing=self.offset+self.pendingDelta
  if math.abs(existing+delta)>self:storedLimit(base) and math.abs(existing+delta)>math.abs(existing) then
   return false,'Stored BPM offset limit reached'
  end
  self.pendingDelta=self.pendingDelta+delta
  self.metrics.tempo_gifts=self.metrics.tempo_gifts+1
 elseif command.kind=='lock' then
  local blocks=command.measures/self.config.lock_min_measures
  if blocks~=math.floor(blocks) or blocks>self:remainingLocks(beat) then return false,'BPM LOCK SOLD OUT' end
  self.lockReserved=self.lockReserved+command.measures
  self.metrics.lock_gifts=self.metrics.lock_gifts+1
 else return false,'Unknown tempo command' end
 command.applyBeat=math.floor(beat+0.000001)+1
 self.actions[#self.actions+1]=command
 self:event(command.event_id,'queued','Applies on next beat')
 return true
end
function R:announce(command,now)
 local last=self.feed[#self.feed]
 if last and last.sender==command.sender and last.bpm_delta==command.bpm_delta and now-last.last_at<=1.5 then
  last.count=last.count+1 last.last_at=now
 else
  self.serial=self.serial+1
  self.feed[#self.feed+1]={event_id='feed-'..self.serial,sender=command.sender,
   bpm_delta=command.bpm_delta,count=1,last_at=now}
 end
 while #self.feed>12 do table.remove(self.feed,1) end
end
function R:apply(command,now)
 self.offset=self.offset+command.bpm_delta
 self.pendingDelta=self.pendingDelta-command.bpm_delta
 self.decayElapsed=0
 self:event(command.event_id,'applied')
 self.appliedThisStep[#self.appliedThisStep+1]=command
 self:announce(command,now)
end
function R:startLock(command,beat)
 self.lock={event_id=command.event_id,sender=command.sender,bpm=self:bpm(self.baseAt(beat)),
  startMeasure=R.measure(beat,self.signatures),measures=command.measures}
 self.lock.endMeasure=self.lock.startMeasure+command.measures
 self.lock.endBeat=R.beat(self.lock.endMeasure,self.signatures)
 self:event(command.event_id,'active')
end
function R:advanceUnlocked(from,to)
 local elapsed=R.measure(to,self.signatures)-R.measure(from,self.signatures)
 self.decayElapsed=self.decayElapsed+math.max(0,elapsed)
 local steps=math.floor((self.decayElapsed+0.000001)/self.config.tempo_decay_measures)
 if steps>0 then
  self.decayElapsed=self.decayElapsed-steps*self.config.tempo_decay_measures
  self.offset=self.offset>0 and math.max(0,self.offset-steps) or math.min(0,self.offset+steps)
 end
end
function R:step(beat,now)
 self.appliedThisStep={}
 if beat<0 then return end
 local cursor=self.lastBeatUpdated
 while cursor<=beat do
  local nextAction=self.actions[1] and self.actions[1].applyBeat or math.huge
  local nextEnd=self.lock and self.lock.endBeat or math.huge
  local due=math.max(cursor,math.min(beat,nextAction,nextEnd))
  if not self.lock then self:advanceUnlocked(cursor,due)
  else
   local elapsed=R.measure(due,self.signatures)-R.measure(cursor,self.signatures)
   self.lockReserved=math.max(0,self.lockReserved-elapsed)
  end
  cursor=due
  if self.lock and self.lock.endBeat<=cursor+0.000001 then
   self:event(self.lock.event_id,'completed')
   self.completedLocks[#self.completedLocks+1]=self.lock.event_id
   while #self.completedLocks>128 do table.remove(self.completedLocks,1) end
   self.lock=nil
   for _,command in ipairs(self.held) do self:apply(command,now) end
   self.held={}
   if #self.locks>0 then self:startLock(table.remove(self.locks,1),cursor) end
  end
  while self.actions[1] and self.actions[1].applyBeat<=cursor+0.000001 do
   local command=table.remove(self.actions,1)
   if command.kind=='tempo' then
    if self.lock then self.held[#self.held+1]=command self:event(command.event_id,'held','Waiting for lock release',self.lock.event_id)
    else self:apply(command,now) end
   elseif self.lock then
    self.locks[#self.locks+1]=command self:event(command.event_id,'reserved','Lock queued')
   else self:startLock(command,cursor) end
  end
  if cursor>=beat then break end
 end
 self.lastBeatUpdated=beat
 for i=#self.feed,1,-1 do if now-self.feed[i].last_at>self.config.tempo_notice_seconds then table.remove(self.feed,i) end end
 local base=self.baseAt(beat)
 self.metrics.max_overflow=math.max(self.metrics.max_overflow,math.max(0,math.abs(self.offset)-self:limit(base)))
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
