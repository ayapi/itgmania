-- ITGmania streaming fork / Simply Love. All gameplay mutations run on the game thread.
local json = dofile(THEME:GetCurrentThemeDirectory().."BGAnimations/ScreenGameplay overlay/GiftAPI.Json.lua")
local Rules = dofile(THEME:GetCurrentThemeDirectory().."BGAnimations/ScreenGameplay overlay/GiftRules.lua")
local directory = "Save/GiftAPI/"
local config = {max_active_arrows=24, max_queued_arrows=512, max_tempo_effects=128,
                min_rate=0.25, max_rate=3, min_lead_seconds=0.8,
                tempo_limit_percent=0.15,tempo_stored_limit_percent=0.50,
                tempo_decay_measures=4,lock_min_measures=4,tempo_notice_seconds=0.8}
local packetCache={}
local screen
local performance={max_update_ms=0,max_insert_ms=0,slow_updates=0}
local function measured(name,callback)
 local started=GetTimeSinceStart()
 callback()
 performance[name]=math.max(performance[name] or 0,(GetTimeSinceStart()-started)*1000)
end
local function read(path)
 local contents
 if path==directory.."commands.json" and screen and screen.GetGiftCommands then
  contents=screen:GetGiftCommands()
 else
  local f=RageFileUtil.CreateRageFile()
  if f:Open(path,1) then contents=f:ReadBytes(1048576) f:Close() end
  f:destroy()
 end
 if not contents or contents=="" then return nil end
 if packetCache[path] and packetCache[path].contents==contents then return packetCache[path].value end
 local ok,value=pcall(json.decode,contents)
 if ok then packetCache[path]={contents=contents,value=value} return value end
 Trace("GiftAPI JSON read failed: "..path.." bytes="..#contents.." "..tostring(value))
end
local function write(path,value)
 if screen and screen.PublishGiftStatus then
  screen:PublishGiftStatus(json.encode(value))
  return
 end
 local f=RageFileUtil.CreateRageFile()
 -- Status is a transient heartbeat, not a persistent save. Stream directly
 -- so Windows readers cannot block a file-replacement operation on the
 -- render thread. The bridge keeps its last complete snapshot during writes.
 if f:Open(path,6) then f:Write(json.encode(value)) f:Close() end
 f:destroy()
end
local configured=read(directory.."config.json")
if configured then
 for k,v in pairs(config) do
  if type(configured[k])=="number" and configured[k]>0 then config[k]=configured[k] end
 end
end
config.max_active_arrows=math.min(64,math.floor(config.max_active_arrows))
config.max_queued_arrows=math.min(2048,math.floor(config.max_queued_arrows))
config.min_rate=math.max(0.1,config.min_rate)
config.max_rate=math.min(3,math.max(config.min_rate,config.max_rate))
config.tempo_limit_percent=math.min(0.15,config.tempo_limit_percent)
config.tempo_stored_limit_percent=math.max(config.tempo_limit_percent,config.tempo_stored_limit_percent)

local state={session="", server_id="", cursor=0, effects={}, queue={}, active={}, results={}, players={}}
local noteFeed={}
local byname, containers, bubbleActors={}, {}, {}
local bpmActor
local noticeActors,tempoNotices={},{}
local bubbleZoom=0.65
local nameFont=FILEMAN:DoesFileExist(THEME:GetCurrentThemeDirectory().."Fonts/Stream Noto Sans JP.ini") and "Stream Noto Sans JP" or "Common Normal"
local rules,lockActor,lifeActor
local inventoryTotal=0
local nextLabelOrder=0
local roundedBubbleVertices
local song, baseline, originalHaste, lastRate, lastPoll, lastStatus
local reason, stopped, initialized="Starting gameplay",false,false
local currentBpm, totalDelta, effectiveRate=0,0,1
local resultById={}
local lastReadyFrame
local lastMetricFrame
local resultPage=0
local function noteKey(beat,column) return tostring(math.floor(beat*48+0.5))..":"..column end
local function scored(note)
 return note[3]=="TapNoteType_Tap" or note[3]=="TapNoteType_Lift" or note[3]=="TapNoteType_HoldHead" or note[3]=="TapNoteSubType_Hold" or note[3]=="TapNoteSubType_Roll"
end
local function track(data,timing)
 local notes={}
 for _,note in ipairs(data) do
  if scored(note) and timing:IsJudgableAtBeat(note[1]) then
   notes[#notes+1]={note[1],note[2],note[3],length=note.length,seconds=timing:GetElapsedTimeFromBeat(note[1])}
  end
 end
 table.sort(notes,function(a,b) if a[1]==b[1] then return a[2]<b[2] end return a[1]<b[1] end)
 return notes
end
local function result(command, status, message)
 local r={event_id=command.event_id, state=status, reason=message or "", inserted=command.inserted or 0}
 state.results[#state.results+1]=r
 resultById[command.event_id]=r
 while #state.results>10000 do
  local old=table.remove(state.results,1)
  if resultById[old.event_id]==old then resultById[old.event_id]=nil end
 end
 return r
end
local function activeCount()
 local n=0
 for _,a in ipairs(state.active) do if not a.done then n=n+1 end end
 return n
end
local function queueCount()
 local n=0
 for _,a in ipairs(state.queue) do n=n+a.remaining end
 return n
end
local function snapshot(ready, message)
 local tempoEffects={}
 local now=GetTimeSinceStart()
 for _,effect in ipairs(state.effects) do
  tempoEffects[#tempoEffects+1]={event_id=effect.event_id,sender=effect.sender or "",
   bpm_delta=effect.delta,remaining_seconds=math.max(0,effect.expires-now)}
 end
 local originalTotal,originalJudged,holds=0,0,0
 for _,p in pairs(byname) do
  for key in pairs(p.original or {}) do originalTotal=originalTotal+1 if p.processed[key] then originalJudged=originalJudged+1 end end
  for _,note in ipairs(p.originalData or {}) do if note.length and note.length>0 then holds=holds+1 end end
 end
 local available=0
 for _,p in pairs(byname) do available=available+(p.planAvailable or 0) end
 local lockStatus=nil
 if rules and rules.lock then
  local l=rules.lock
  local master=byname[ToEnumShortString(GAMESTATE:GetMasterPlayerNumber())]
  local remaining=(master.timing:GetElapsedTimeFromBeat(l.endBeat)-GAMESTATE:GetSongPosition():GetMusicSeconds())/effectiveRate
  lockStatus={sender=l.sender,event_id=l.event_id,remaining_seconds=math.max(0,remaining),end_beat=l.endBeat,
   queued=#rules.locks,bpm=l.bpm}
 end
 local life,failed=1,false
 local masterNumber=GAMESTATE:GetMasterPlayerNumber()
 local meter=screen and screen:GetLifeMeter(masterNumber)
 if meter then life=meter:GetLife() end
 local stats=STATSMAN:GetCurStageStats():GetPlayerStageStats(masterNumber)
 failed=stats:GetFailed()
 local segments=0
 for _,combo in ipairs(stats:GetComboList()) do if combo.Count>0 then segments=segments+1 end end
 local judgments={}
 for _,name in ipairs({"W1","W2","W3","W4","W5","Miss"}) do
  judgments[name]=stats:GetTapNoteScores("TapNoteScore_"..name)
 end
 judgments.Held=stats:GetHoldNoteScores("HoldNoteScore_Held")
 judgments.LetGo=stats:GetHoldNoteScores("HoldNoteScore_LetGo")
 -- Rotate bounded receipt pages. Held/queued events keep their final
 -- outcome even during a busy lock, without serializing all history at 60fps.
 local receipts={}
 if #state.results>0 then
  resultPage=resultPage%#state.results
  for i=1,math.min(512,#state.results) do receipts[i]=state.results[(resultPage+i-1)%#state.results+1] end
  resultPage=(resultPage+#receipts)%#state.results
 end
 write(directory.."status.json",{protocol_version=3,ready=ready,reason=message or "",session=state.session,
  server_id=state.server_id,cursor=state.cursor,players=state.players,results=receipts,
  song=song and song:GetDisplayMainTitle() or "", base_bpm=currentBpm,
  song_title=song and song:GetDisplayFullTitle() or "",
  song_artist=song and song:GetDisplayArtist() or "",
  active_tempo_effects=tempoEffects,
  tempo_feed=rules and rules.feed or {},bpm_offset=rules and rules.offset or 0,
  native_tempo_notice=true,tempo_notice=tempoNotices,
  note_feed=noteFeed,
  pending_bpm_delta=rules and rules.pendingDelta or 0,
  bpm_offset_limit=rules and rules:limit(currentBpm) or 0,
  bpm_stored_limit=rules and rules:storedLimit(currentBpm) or 0,
  bpm_overflow=rules and math.max(0,math.abs(rules.offset)-rules:limit(currentBpm)) or 0,
  bpm_lock=lockStatus,lock_min_measures=config.lock_min_measures,
  completed_locks=rules and rules.completedLocks or {},
  lock_remaining=rules and rules:remainingLocks(GAMESTATE:GetSongPosition():GetSongBeat()) or 0,
  note_slots_total=inventoryTotal,note_remaining=math.max(0,available-queueCount()),
  life=life,failed=failed,metrics=rules and rules.metrics or {},
  current_combo=stats:GetCurrentCombo(),max_combo=stats:MaxCombo(),
  combo_breaks=math.max(0,segments-(stats:GetCurrentCombo()>0 and 1 or 0)),judgments=judgments,
  stream_mirror=SL.StreamMirrorOffsetX~=nil,
  stream_mirror_offset_pixels=(SL.StreamMirrorOffsetX or 0)*DISPLAY:GetDisplayWidth()/SCREEN_WIDTH,
  bpm_delta=totalDelta, effective_bpm=currentBpm*effectiveRate, rate=effectiveRate,
  active_arrows=activeCount(), queued_arrows=queueCount(), tempo_effects=#state.effects,
  original_notes=originalTotal, judged_original_notes=originalJudged,
  hold_intervals=holds,
  performance=performance,
  mailbox_async=screen and screen.GetGiftCommands~=nil or false,
  fps=DISPLAY:GetFPS(),
  song_beat=GAMESTATE:GetSongPosition():GetSongBeat(),
  music_seconds=GAMESTATE:GetSongPosition():GetMusicSeconds(),
  saturated=rules and math.abs(totalDelta)>=rules:limit(currentBpm) or false})
end
local function songOptions(level) return GAMESTATE:GetSongOptionsObject(level) end
local function applyRate(rate)
 if not lastRate or math.abs(rate-lastRate)>0.00001 then
  songOptions("ModsLevel_Song"):MusicRate(rate)
  songOptions("ModsLevel_Current"):MusicRate(rate)
  -- Apply the same rate to the native sound parameters, including changes
  -- smaller than ScreenGameplay's automatic update threshold. Do not seek.
  screen:GetSound():SetParam("Speed",rate)
  lastRate=rate
 end
 effectiveRate=rate
end
local function resetRate()
 if initialized then
  songOptions("ModsLevel_Song"):MusicRate(baseline)
  songOptions("ModsLevel_Current"):MusicRate(baseline)
  screen:GetSound():SetParam("Speed",baseline)
  songOptions("ModsLevel_Song"):Haste(originalHaste)
  songOptions("ModsLevel_Current"):Haste(originalHaste)
  effectiveRate=baseline
 end
 lastRate=nil
end
local function modified()
 -- Modified charts must not replace personal bests for the original chart.
 -- Native judgments, combo, life and the on-screen score remain enabled.
 songOptions("ModsLevel_Song"):SaveScore(false)
 songOptions("ModsLevel_Current"):SaveScore(false)
end
local function initialize()
 screen=SCREENMAN:GetTopScreen()
 song=GAMESTATE:GetCurrentSong()
 if not song or GAMESTATE:IsDemonstration() or GAMESTATE:IsCourseMode() then
  reason="GiftAPI supports normal single-song gameplay" return false
 end
 if GAMESTATE:GetCurrentGame():GetName()~="dance" or GAMESTATE:GetCurrentStyle():ColumnsPerPlayer()~=4 then
  reason="GiftAPI supports dance-single (4 arrows)" return false
 end
 byname={}
 inventoryTotal=0
 state.players={}
 for _,pn in ipairs(GAMESTATE:GetHumanPlayers()) do
  local name=ToEnumShortString(pn)
  local actor=screen:GetChild("Player"..name)
  local ps=GAMESTATE:GetPlayerState(pn)
  if not actor then reason="Player actor is unavailable" return false end
  if ps:GetCurrentPlayerOptions():UsingReverse() then
   reason="GiftAPI requires normal upward scroll" return false
  end
  byname[name]={pn=pn,actor=actor,ps=ps,field=actor:GetChild("NoteField"),
                timing=GAMESTATE:GetCurrentSteps(pn):GetTimingData(),steps=GAMESTATE:GetCurrentSteps(pn)}
  local p=byname[name]
  p.originalData=actor:GetNoteData()
  p.mineTimes={}
  for _,note in ipairs(p.originalData) do
   if note[3]=="TapNoteType_Mine" and p.timing:IsJudgableAtBeat(note[1]) then p.mineTimes[#p.mineTimes+1]=p.timing:GetElapsedTimeFromBeat(note[1]) end
  end
  p.tracked=track(p.originalData,p.timing) p.processed={} p.original={} p.pendingIndex=1
  p.lastBeat=0
  for _,n in ipairs(p.originalData) do p.lastBeat=math.max(p.lastBeat,n[1]+(n.length or 0)) end
  p.notePlan=Rules.notePlan(p.originalData,p.lastBeat,function(beat)
   if not p.timing:IsJudgableAtBeat(beat) then return false end
   local seconds=p.timing:GetElapsedTimeFromBeat(beat)
   for _,mine in ipairs(p.mineTimes) do if math.abs(seconds-mine)<0.2 then return false end end
   return true
  end)
  p.planAvailable=#p.notePlan p.planCursor=1
  inventoryTotal=inventoryTotal+#p.notePlan
  for _,level in ipairs({"ModsLevel_Stage","ModsLevel_Song","ModsLevel_Current"}) do
   ps:GetPlayerOptions(level):FailSetting("FailType_EndOfSong")
  end
  for _,note in ipairs(p.tracked) do p.original[noteKey(note[1],note[2])]=true end
  state.players[#state.players+1]=name
 end
 baseline=songOptions("ModsLevel_Current"):MusicRate()
 originalHaste=songOptions("ModsLevel_Current"):Haste()
 if originalHaste~=0 then reason="Turn off Haste before using GiftAPI" return false end
 state.session=tostring(GetTimeSinceStart()).."-"..tostring(math.random(1,100000000))
 state.effects={} state.queue={} state.active={} state.results={} resultById={}
 state.cursor=0 state.server_id=""
 local master=byname[ToEnumShortString(GAMESTATE:GetMasterPlayerNumber())]
 local lastBeat=master.timing:GetBeatFromElapsedTime(song:GetLastSecond())
 rules=Rules.new(config,lastBeat,master.timing:GetTimeSignatures(true),function(beat) return master.timing:GetBPMAtBeat(beat) end)
 GAMESTATE:SetFailTypeExplicitlySet()
 initialized=true stopped=false reason=""
 return true
end
local function consume(now)
 local packet=read(directory.."commands.json")
 if type(packet)~="table" or type(packet.commands)~="table" then return end
 if packet.server_id~=state.server_id then
  state.server_id=packet.server_id state.cursor=0
 end
 for _,command in ipairs(packet.commands) do
  if command.sequence>state.cursor then
   state.cursor=command.sequence
   if command.session~=state.session then
    result(command,"discarded","Command belongs to another song")
   elseif command.kind=="tempo" or command.kind=="lock" then
    local accepted,why=rules:submit(command,GAMESTATE:GetSongPosition():GetSongBeat())
    if accepted then
     modified()
     result(command,"queued")
    else result(command,"rejected",why) end
   elseif command.kind=="notes" then
    if not byname[command.player] then result(command,"rejected","Player is unavailable")
    elseif command.count>math.max(0,byname[command.player].planAvailable-queueCount()) then result(command,"rejected","NOTE ATTACK SOLD OUT")
    elseif queueCount()+command.count>config.max_queued_arrows then result(command,"rejected","Arrow queue is full")
    else
     modified()
     command.remaining=command.count command.inserted=0
     rules.metrics.note_gifts=(rules.metrics.note_gifts or 0)+1
     rules.metrics.note_units_accepted=(rules.metrics.note_units_accepted or 0)+command.count
     state.queue[#state.queue+1]=command
     noteFeed[#noteFeed+1]={event_id=command.event_id,sender=command.sender,count=command.count,last_at=now}
     while #noteFeed>3 do table.remove(noteFeed,1) end
     result(command,"queued")
    end
   else result(command,"rejected","Unknown command") end
  end
 end
end
local function updateTempo(now)
 local master=byname[ToEnumShortString(GAMESTATE:GetMasterPlayerNumber())]
 if not master then return end
 local beat=master.ps:GetSongPosition():GetSongBeat()
 local beforeBpm=currentBpm*effectiveRate
 currentBpm=master.timing:GetBPMAtBeat(beat)
 rules:step(beat,now)
 for id,event in pairs(rules.changes) do
  local r=resultById[id] if r then r.state=event.state r.reason=event.reason r.lock_event_id=event.lock_event_id end
 end
 rules.changes={}
 if currentBpm>0 then
  local limit=rules:limit(currentBpm)
  local bpm=math.max(currentBpm-limit,math.min(currentBpm+limit,rules:bpm(currentBpm)))
  totalDelta=bpm-currentBpm
  applyRate(bpm/currentBpm)
  if math.abs(bpm-beforeBpm)>0.01 then
   for _,command in ipairs(rules.appliedThisStep) do
    local last=tempoNotices[#tempoNotices]
    if last and last.sender==command.sender and last.bpm_delta==command.bpm_delta and now-last.last_at<=config.tempo_notice_seconds then
     last.count=last.count+1 last.last_at=now
    else
     tempoNotices[#tempoNotices+1]={sender=command.sender,bpm_delta=command.bpm_delta,count=1,last_at=now,actual_bpm=bpm}
    end
   end
   while #tempoNotices>3 do table.remove(tempoNotices,1) end
  end
 end
 for i=#tempoNotices,1,-1 do if now-tempoNotices[i].last_at>config.tempo_notice_seconds then table.remove(tempoNotices,i) end end
end
local function geometry(p, beat, column)
 local yoffset=ArrowEffects.GetYOffset(p.ps,column,beat)
 local y=ArrowEffects.GetYPos(p.ps,column,yoffset)
 local x=ArrowEffects.GetXPos(p.ps,column,yoffset)
 local fx=p.field and p.field:GetX() or 0
 local fy=p.field and p.field:GetY() or 0
 local zx=p.field and p.field:GetZoomX() or 1
 local zy=p.field and p.field:GetZoomY() or 1
 return fx+x*zx,fy+y*zy,yoffset
end
local function refreshInventory()
 for _,p in pairs(byname) do
  local pos=p.ps:GetSongPosition()
  local first=pos:GetSongBeat()+math.max(0.5,currentBpm*effectiveRate/60*config.min_lead_seconds)
  while p.notePlan and p.notePlan[p.planCursor] do
   local n=p.notePlan[p.planCursor]
   if n.used then p.planCursor=p.planCursor+1
   else
    local _,y=geometry(p,n.beat,n.column)
    local screenY=p.actor:GetY()+y*p.actor:GetZoomY()
    if n.beat<first or screenY<SCREEN_HEIGHT-12 then
     n.used=true p.planAvailable=p.planAvailable-1 p.planCursor=p.planCursor+1
    else break end
   end
  end
 end
end
local function plannedSlot(p,sideCounts,selected)
 for i=p.planCursor,#p.notePlan do
  local n=p.notePlan[i]
  local side=n.column>=3 and 1 or 2
  if not n.used and not selected[i] and (not sideCounts or sideCounts[side]<3) then
   return n.beat,n.column,i
  end
 end
end
local function occupancyIndex(data)
 local index={rows={},holds={},lastBeat=0}
 for _,note in ipairs(data) do
  local row=math.floor(note[1]*48+0.5)
  index.rows[row]=index.rows[row] or {occupied={},feet={}}
  index.rows[row].occupied[note[2]]=true
  if scored(note) then index.rows[row].feet[note[2]]=true end
  if note.length and note.length>0 then index.holds[#index.holds+1]=note end
  index.lastBeat=math.max(index.lastBeat,note[1]+(note.length or 0))
 end
 return index
end
local function occupancyAt(index,beat)
 local row=index.rows[math.floor(beat*48+0.5)]
 local occupied,requiredColumns={},{}
 if row then
  for col in pairs(row.occupied) do occupied[col]=true end
  for col in pairs(row.feet) do requiredColumns[col]=true end
 end
 for _,note in ipairs(index.holds) do
  if beat>=note[1] and beat<=note[1]+note.length then
   occupied[note[2]]=true
   if scored(note) then requiredColumns[note[2]]=true end
  end
 end
 local feet=0
 for _ in pairs(requiredColumns) do feet=feet+1 end
 return occupied,feet
end
local function giftGrid(backlog)
 return 0.5 -- Version 3 inventory is eighth-note only, even during a backlog.
end
-- P1 columns 3/4 become down/left in the reversed stream copy.
local function bubbleSide(column) return column>=3 and 1 or 2 end
local function slot(p,index,grid,sideCounts)
 grid=grid or 0.5 -- Eighth notes normally; sixteenths only for a large backlog.
 local position=p.ps:GetSongPosition()
 local beat=position:GetSongBeat()
 local first=math.ceil((beat+math.max(0.5,currentBpm*effectiveRate/60*config.min_lead_seconds))/grid)*grid
 if not p.lastBeat then
  p.lastBeat=index.lastBeat
 end
 local ending=math.min(first+128,p.lastBeat-grid)
 local startcol=math.random(1,4)
 local bottom=SCREEN_HEIGHT-12
 for b=first,ending,grid do
  if p.timing:IsJudgableAtBeat(b) then
   local occupied,feet=occupancyAt(index,b)
   if feet<2 then
   for c=0,3 do
    local col=(startcol+c-1)%4+1
    if not occupied[col] and (not sideCounts or sideCounts[bubbleSide(col)]<3) then
    local _,y=geometry(p,b,col)
    local screenY=p.actor:GetY()+y*p.actor:GetZoomY()
    if screenY>=bottom then return b,col end
    end
   end
   end
  end
 end
end
local function updatePointLimits()
 for _,p in pairs(byname) do
  if p.pendingPoints and p.pendingPoints>0 then
   local stats=STATSMAN:GetCurStageStats():GetPlayerStageStats(p.pn)
   local actual=stats:GetActualDancePoints()
   -- This build rejects negative actual values in both dance-point setters.
   -- A negative score is already displayed as zero. Preserve the native
   -- value and update its denominator as soon as the score recovers.
   if actual>=0 then
    stats:SetDancePointLimits(actual,stats:GetPossibleDancePoints()+p.pendingPoints)
    p.pendingPoints=0
   end
  end
 end
end
local function insertNotes()
 -- Six stationary cards fit beside the face; defer excess notes rather
 -- than introducing real gift arrows whose sender cannot be displayed.
 local capacity=PREFSMAN:GetPreference("StreamerMode") and math.min(6,config.max_active_arrows) or config.max_active_arrows
 if #state.queue==0 or activeCount()>=capacity then return end
 local command=state.queue[1]
 local p=byname[command.player]
 local data=p.actor:GetNoteData()
 local index=occupancyIndex(data)
 local added={}
 local selected={}
 local sideCounts
 if PREFSMAN:GetPreference("StreamerMode") then
  sideCounts={0,0}
  for _,note in ipairs(state.active) do
   if not note.done then local side=bubbleSide(note.column) sideCounts[side]=sideCounts[side]+1 end
  end
 end
 local grid=giftGrid(queueCount())
 while command.remaining>0 and #added<4 and activeCount()+#added<capacity do
  local beat,col,planIndex=plannedSlot(p,sideCounts,selected)
  if not beat then
   break -- Keep accepted notes queued and retry as active cards clear.
  end
  data[#data+1]={beat,col,"TapNoteType_Tap",grid==0.5 and "TapNote_8th" or "TapNote_16th"}
  local row=math.floor(beat*48+0.5)
  index.rows[row]=index.rows[row] or {occupied={},feet={}}
  index.rows[row].occupied[col]=true index.rows[row].feet[col]=true
  selected[planIndex]=true
  added[#added+1]={beat=beat,column=col,planIndex=planIndex,player=command.player,sender=command.sender,event_id=command.event_id,done=false}
  if sideCounts then local side=bubbleSide(col) sideCounts[side]=sideCounts[side]+1 end
  command.remaining=command.remaining-1
 end
 if #added>0 then
  local taps={}
  for _,note in ipairs(added) do taps[#taps+1]={note.beat,note.column} end
  if not p.actor:AddGiftTapNotes(taps) then
   command.remaining=command.remaining+#added
   Trace("GiftAPI: native insertion deferred")
   return
  end
  p.tracked=track(data,p.timing) p.pendingIndex=1
  p.pendingPoints=(p.pendingPoints or 0)+#added*THEME:GetMetric("ScoreKeeperNormal","PercentScoreWeightW1")
  updatePointLimits()
  for _,note in ipairs(added) do
   p.notePlan[note.planIndex].used=true p.planAvailable=p.planAvailable-1
   nextLabelOrder=nextLabelOrder+1 note.labelOrder=nextLabelOrder
   state.active[#state.active+1]=note
  end
  rules.metrics.note_units_inserted=(rules.metrics.note_units_inserted or 0)+#added
  command.inserted=command.inserted+#added
  local r=resultById[command.event_id]
  if r then r.inserted=command.inserted end
 end
 if command.remaining==0 then
  local r=resultById[command.event_id]
  if r then r.state="inserted" end
  if state.queue[1]==command then table.remove(state.queue,1) end
 end
end
local function hide(note)
 note.done=true
 if note.bubble and bubbleActors[note.bubble] then bubbleActors[note.bubble]:visible(false) end
 note.bubble=nil
end
local function screenPosition(p,beat,column)
 local x,y,offset=geometry(p,beat,column)
 return p.actor:GetX()+x*p.actor:GetZoomX(),p.actor:GetY()+y*p.actor:GetZoomY(),offset
end
local function railBounds()
 local left,right=SCREEN_WIDTH,0
 for _,p in pairs(byname) do
  local beat=p.ps:GetSongPosition():GetSongBeat()
  -- The skin uses 64-unit arrows. Leave a small gap outside their edge
  -- rather than reserving the old 80-unit box plus 12 units of padding.
  local half=32*math.abs(p.actor:GetZoomX()*(p.field and p.field:GetZoomX() or 1))
  for col=1,4 do
   local x=screenPosition(p,beat,col)
   left=math.min(left,x-half) right=math.max(right,x+half)
  end
 end
 return left-4,right+4
end
local function formatSender(name,measure,width)
 -- Split at UTF-8 character boundaries, including names without spaces.
 local lines={""}
 local function trimLast(text) return (text:gsub("[%z\1-\127\194-\244][\128-\191]*$","")) end
 for char in name:gmatch("[%z\1-\127\194-\244][\128-\191]*") do
  local row=#lines
  if measure(lines[row]..char)<=width then
   lines[row]=lines[row]..char
  elseif row==1 and lines[1]~="" then
   lines[2]=char
  else
   while lines[row]~="" and measure(lines[row].."...")>width do lines[row]=trimLast(lines[row]) end
   lines[row]=lines[row].."..."
   return table.concat(lines,"\n")
  end
 end
 return table.concat(lines,"\n")
end
local function drawLabelTarget(actor,layout,targetX)
 local dx,dy=targetX-layout.edge,layout.arrowY-layout.y
 actor:GetChild("Leader"):xy((layout.edge+targetX)/2-layout.x,dy/2)
  :zoomto(math.sqrt(dx*dx+dy*dy),1):rotationz(math.atan2(dy,dx)*180/math.pi)
 actor:GetChild("Target"):xy(targetX-layout.x,dy)
end
local function updateBubbles()
 local used,visible={},{}
 for _,note in ipairs(state.active) do if not note.done and note.bubble then used[note.bubble]=true end end
 for _,note in ipairs(state.active) do
  if not note.done then
   local p=byname[note.player]
   local pos=p.ps:GetSongPosition()
   if pos:GetMusicSeconds()>p.timing:GetElapsedTimeFromBeat(note.beat)+0.5*effectiveRate then hide(note)
   else
    if not note.bubble then
     for i=1,config.max_active_arrows do
      if not used[i] then note.bubble=i used[i]=true break end
     end
    end
    local a=note.bubble and bubbleActors[note.bubble]
    if a then
     a:visible(false)
     local px,py,offset=screenPosition(p,note.beat,note.column)
     local alpha=ArrowEffects.GetAlpha(p.ps,note.column,offset)
     local streamOffsetY=SL.StreamMirrorOffsetY or 0
     if py>=0 and py<=SCREEN_HEIGHT-streamOffsetY and alpha>0 then
      visible[#visible+1]={note=note,actor=a,p=p,x=px,y=py}
     end
    end
   end
  end
 end
 local sides={{},{}}
 for _,item in ipairs(visible) do
  if not item.note.formattedName then
   local text=item.actor:GetChild("Sender")
   text:maxwidth(0)
   item.note.formattedName=formatSender(item.note.sender,function(value)
    text:settext(value)
    return text:GetWidth()*bubbleZoom
   end,70)
   text:settext(item.note.formattedName):maxwidth(0)
   -- Three logical pixels of padding on each edge; short names and one-line
   -- names no longer reserve a full two-line card.
   item.note.labelWidth=math.min(76,math.max(16,text:GetWidth()*bubbleZoom+6))
   item.note.labelHeight=math.max(16,text:GetHeight()*bubbleZoom+6)
   local vertices=roundedBubbleVertices(item.note.labelWidth,item.note.labelHeight,3)
   item.actor:GetChild("Background"):SetNumVertices(#vertices):SetVertices(vertices)
  end
  if item.note.labelSide then table.insert(sides[item.note.labelSide],item) end
 end
 for _,item in ipairs(visible) do
  if not item.note.labelSide then
   local side=bubbleSide(item.note.column)
   item.note.labelSide=side
   table.insert(sides[side],item)
  end
 end
 -- Stable insertion order: names never follow note scrolling. Only a
 -- new/finished neighbour changes their slot, with a short slide tween.
 for side,items in ipairs(sides) do
  table.sort(items,function(a,b) return a.note.labelOrder<b.note.labelOrder end)
  local y=68
  for rank=#items,1,-1 do
   local item=items[rank]
   local width=item.note.labelWidth
   -- Widen towards BPM while keeping the same outer capture boundary.
   local distance=143-width/2
   local x=item.p.actor:GetX()+(side==1 and -distance or distance)
   local edge=x+(side==1 and width/2 or -width/2)
   local half=25*math.abs(item.p.actor:GetZoomX()*(item.p.field and item.p.field:GetZoomX() or 1))
   local targetX=item.x+(side==1 and -half or half)
   local a=item.actor
   if item.note.labelY==nil then
    a:finishtweening():xy(x,y+8):diffusealpha(0):decelerate(0.16):y(y):diffusealpha(1)
   elseif item.note.labelY~=y then
    a:stoptweening():decelerate(0.16):y(y)
   end
   item.note.labelY=y
   a:visible(true)
   item.note.labelGeometry={x=x,y=a:GetY(),edge=edge,arrowY=item.y,targetX=targetX,
    mirrorTargetX=2*item.p.actor:GetX()-item.x+(side==1 and -half or half)}
   drawLabelTarget(a,item.note.labelGeometry,targetX)
   if rank>1 then y=y-item.note.labelHeight/2-items[rank-1].note.labelHeight/2-2 end
  end
 end
 for i=#state.active,1,-1 do if state.active[i].done then table.remove(state.active,i) end end
end
local function judged(params)
 if not initialized or not params.Player then return end
 local p=byname[ToEnumShortString(params.Player)]
 if not p then return end
 local seconds=p.ps:GetSongPosition():GetMusicSeconds()
 if params.HoldNoteScore then
  -- A completely missed hold head is reported through Holds/MissedHold,
  -- rather than through a normal tap-row judgment on this build.
  local columns=params.Holds or (params.FirstTrack and {[params.FirstTrack+1]=true}) or {}
  for col in pairs(columns) do
   for _,note in ipairs(p.tracked) do
    if note[2]==col and note.length and note.length>0 and note.seconds<=seconds and not p.processed[noteKey(note[1],col)] then
     p.processed[noteKey(note[1],col)]=true
     p.latestProcessedTime=math.max(p.latestProcessedTime or -math.huge,note.seconds)
     break
    end
   end
  end
  return
 end
 if not params.Notes or not params.TapNoteScore then return end
 local score=params.TapNoteScore
 if score~="TapNoteScore_Miss" and not score:match("^TapNoteScore_W[1-5]$") then return end
 for col,tap in pairs(params.Notes) do
  local result=tap:GetTapNoteResult()
  local kind=tap:GetTapNoteType()
  -- Missed hold heads can have an unset per-note result. The row judgment
  -- is authoritative, just as in Simply Love's per-column score tracking.
  if kind=="TapNoteType_Tap" or kind=="TapNoteType_HoldHead" or kind=="TapNoteType_Lift" then
   local target=seconds-(params.TapNoteOffset or result:GetTapNoteOffset())*effectiveRate
   local matched,dist=nil,math.huge
   for _,note in ipairs(p.tracked) do
    if note[2]==col and not p.processed[noteKey(note[1],col)] then
     local time=note.seconds
     if score=="TapNoteScore_Miss" then
      if time<=seconds then matched=note break end
     else
      local d=math.abs(time-target)
      if d<dist then matched=note dist=d end
     end
    end
   end
   if matched then
    p.processed[noteKey(matched[1],col)]=true
    p.latestProcessedTime=math.max(p.latestProcessedTime or -math.huge,matched.seconds)
    for _,note in ipairs(state.active) do
     if not note.done and note.player==ToEnumShortString(params.Player) and note.column==col and math.abs(note.beat-matched[1])<1/96 then hide(note) end
    end
   end
  end
 end
end
local function finish(message)
 for _,note in ipairs(state.active) do hide(note) end
 for _,r in ipairs(state.results) do
  if r.state=="queued" or r.state=="active" or r.state=="held" or r.state=="reserved" then r.state="discarded" r.reason=message end
 end
 state.active={} state.queue={} state.effects={}
 totalDelta=0
 resetRate()
 stopped=true
 snapshot(false,message)
end
local af=Def.ActorFrame{
 Name="SimplyLoveGiftAPI",
 StreamMirrorDrawCommand=function(self)
  -- Stationary cards on both sides share the stream copy's transform;
  -- only the thin leader endpoints follow reflected note positions.
  for _,note in ipairs(state.active) do
   local actor=note.bubble and bubbleActors[note.bubble]
   local layout=note.labelGeometry
   if not note.done and actor and actor:GetVisible() and layout then
    drawLabelTarget(actor,layout,layout.mirrorTargetX)
    actor:Draw()
    drawLabelTarget(actor,layout,layout.targetX)
   end
  end
  if bpmActor and bpmActor:GetVisible() then bpmActor:Draw() end
  if lockActor and lockActor:GetVisible() then lockActor:Draw() end
  if lifeActor and lifeActor:GetVisible() then lifeActor:Draw() end
  for _,actor in ipairs(noticeActors) do if actor:GetVisible() then actor:Draw() end end
 end,
 OnCommand=function(self)
  initialize()
  lastPoll=0 lastStatus=0
  self:SetUpdateFunction(function()
   local now=GetTimeSinceStart()
   local ok,err=pcall(function()
    if stopped then return end
    if not initialized then
     if now-lastStatus>=0.25 then snapshot(false,reason) lastStatus=now end
     return
    end
    if GAMESTATE:GetCurrentSong()~=song then finish("Song changed") return end
    local pos=GAMESTATE:GetSongPosition()
    local beat=pos:GetSongBeat()
    local ready=beat>=0 and pos:GetMusicSeconds()<song:GetLastSecond() and not screen:IsPaused()
    if ready then
     if lastReadyFrame then
      local gap=(now-lastReadyFrame)*1000
      performance.max_frame_gap_ms=math.max(performance.max_frame_gap_ms or 0,gap)
      if gap>33.4 then performance.slow_frames=(performance.slow_frames or 0)+1 end
     end
     lastReadyFrame=now
    else lastReadyFrame=nil end
    measured("max_tempo_ms",function() updateTempo(now) end)
    for i=#noteFeed,1,-1 do if now-noteFeed[i].last_at>2 then table.remove(noteFeed,i) end end
    if ready and lastMetricFrame and math.abs(totalDelta)>=rules:limit(currentBpm) and totalDelta~=0 then
     rules.metrics.cap_seconds=rules.metrics.cap_seconds+math.max(0,now-lastMetricFrame)
    end
    lastMetricFrame=ready and now or nil
    refreshInventory()
    if ready and now-lastPoll>=0.1 then measured("max_commands_ms",function() consume(now) end) lastPoll=now end
    if ready then
     local started=GetTimeSinceStart()
     insertNotes()
     performance.max_insert_ms=math.max(performance.max_insert_ms,(GetTimeSinceStart()-started)*1000)
    end
    if bpmActor then
     local master=byname[ToEnumShortString(GAMESTATE:GetMasterPlayerNumber())]
     bpmActor:visible(ready and master~=nil)
     if master then
      local phase=beat-math.floor(beat)
      local pulse=1+0.12*math.exp(-phase*12)
      bpmActor:xy(master.actor:GetX(),68):zoom(pulse)
      local bpm=currentBpm*effectiveRate
      local colorName=bpm>currentBpm+0.01 and "Up" or bpm<currentBpm-0.01 and "Down" or "Base"
      local value=string.format("%.1f",bpm):gsub("%.0$","")
      for _,name in ipairs({"Base","Up","Down"}) do
       local text=bpmActor:GetChild(name)
       text:visible(name==colorName):settext("BPM"..value.."("..string.format("%+.0f",totalDelta)..")")
       text:zoom(math.min(0.8,115/math.max(1,text:GetWidth())))
      end
      if lockActor then
       local lock=rules.lock
       lockActor:xy(master.actor:GetX(),39):visible(lock~=nil and ready)
       if lock then
        local measures=math.max(0,lock.endMeasure-Rules.measure(beat,rules.signatures))
        lockActor:settext("LOCK "..lock.sender.." "..string.format("%.1f",measures).."小節")
        lockActor:zoom(math.min(0.65,128/math.max(1,lockActor:GetWidth())))
       end
      end
      if lifeActor then
       local meter=screen:GetLifeMeter(master.pn)
       local life=meter and meter:GetLife() or 1
       if not master.lifeY then
        local layout=GetGameplayLayout(master.pn,master.ps:GetPlayerOptions("ModsLevel_Current"):Reverse()>0.5)
        master.lifeY=(layout.Judgment.y+layout.Combo.y)/2
       end
       lifeActor:xy(master.actor:GetX(),master.lifeY):visible(ready)
       lifeActor:GetChild("Fill"):zoomto(128*math.max(0,life),5):diffuse(life<0.25 and color("#ff4040") or color("#39d638"))
      end
      for i,actor in ipairs(noticeActors) do
       local notice=tempoNotices[i]
       actor:visible(ready and notice~=nil)
       if notice then
        local sender=actor:GetChild("Sender")
        if not notice.displayName then
         local short=notice.sender
         sender:settext(short)
         while sender:GetWidth()*0.7>75 and #short>0 do
          short=short:gsub("[%z\1-\127\194-\244][\128-\191]*$","")
          sender:settext(short.."...")
         end
         notice.displayName=short..(short~=notice.sender and "..." or "")
        end
        sender:settext(notice.displayName)
        local selected=notice.bpm_delta>0 and "Up" or "Down"
        local delta=actor:GetChild(selected)
        delta:settext(string.format("%+d",notice.bpm_delta)..(notice.count>1 and " x"..notice.count or ""))
        delta:zoom(math.min(0.65,40/math.max(1,delta:GetWidth())))
        local nw,dw=sender:GetZoomedWidth(),delta:GetZoomedWidth()
        sender:x(-(nw+dw+4)/2)
        for _,name in ipairs({"Up","Down"}) do actor:GetChild(name):visible(name==selected):x((nw-dw+4)/2) end
        actor:xy(master.actor:GetX(),(rules.lock and 15 or 43)-(#tempoNotices-i)*15)
        actor:diffusealpha(math.min(1,(config.tempo_notice_seconds-(now-notice.last_at))/0.12))
       end
      end
     end
    end
    measured("max_points_ms",updatePointLimits)
    measured("max_bubbles_ms",updateBubbles)
    if now-lastStatus>=0.1 then
     measured("max_status_ms",function() snapshot(ready,ready and "" or "Song has not started, has ended, or is paused") end) lastStatus=now
    end
   end)
   local elapsed=(GetTimeSinceStart()-now)*1000
   performance.max_update_ms=math.max(performance.max_update_ms,elapsed)
   if elapsed>16.7 then performance.slow_updates=performance.slow_updates+1 end
   if not ok then
    Trace("GiftAPI error: "..tostring(err))
    finish("GiftAPI error: "..tostring(err))
   end
  end)
 end,
 JudgmentMessageCommand=function(self,p)
  local ok,err=pcall(judged,p)
  if not ok then Trace("GiftAPI judgment tracking: "..tostring(err)) end
 end,
 OffCommand=function(self) if initialized then finish("Gameplay ended") end end,
}
roundedBubbleVertices=function(width,height,radius)
 local white={1,1,1,1}
 local vertices={{{0,0,0},white}}
 local corners={{width/2-radius,-height/2+radius,-90},
                {width/2-radius,height/2-radius,0},
                {-width/2+radius,height/2-radius,90},
                {-width/2+radius,-height/2+radius,180}}
 for _,corner in ipairs(corners) do
  for step=0,8 do
   local angle=math.rad(corner[3]+step*90/8)
   vertices[#vertices+1]={{corner[1]+radius*math.cos(angle),corner[2]+radius*math.sin(angle),0},white}
  end
 end
 vertices[#vertices+1]=vertices[2]
 return vertices
end
local bpm=Def.ActorFrame{
 Name="StreamBPM",
 InitCommand=function(self) bpmActor=self self:visible(false) end,
}
for _,name in ipairs({"Base","Up","Down"}) do
 local hasFont=FILEMAN:DoesFileExist(THEME:GetCurrentThemeDirectory().."Fonts/Stream BPM "..name..".ini")
 bpm[#bpm+1]=LoadFont(hasFont and "Stream BPM "..name or "Common Normal")..{
  Name=name,
  InitCommand=function(self) self:zoom(0.8):diffuse(1,1,1,1):shadowlength(0):visible(false) end,
 }
end
af[#af+1]=bpm
af[#af+1]=LoadFont(nameFont)..{
 Name="StreamLock",
 InitCommand=function(self) lockActor=self self:zoom(0.65):diffuse(1,1,1,1):shadowlength(1):visible(false) end,
}
af[#af+1]=Def.ActorFrame{
 Name="StreamLife",
 InitCommand=function(self) lifeActor=self self:visible(false) end,
 Def.Quad{Name="Frame",InitCommand=function(self) self:zoomto(132,9):diffuse(1,1,1,1) end},
 Def.Quad{InitCommand=function(self) self:zoomto(128,5):diffuse(0,0,0,0.9) end},
 Def.Quad{Name="Fill",InitCommand=function(self) self:halign(0):x(-64):zoomto(128,5):diffuse(0.2,0.8,0.2,1) end},
}
for i=1,3 do
 local index=i
 local notice=Def.ActorFrame{
  Name="StreamTempoNotice"..i,
  InitCommand=function(self) noticeActors[index]=self self:visible(false) end,
  LoadFont(nameFont)..{Name="Sender",InitCommand=function(self) self:halign(0):zoom(0.7):diffuse(1,1,1,1):shadowlength(1) end},
 }
 for _,name in ipairs({"Up","Down"}) do
  local hasFont=FILEMAN:DoesFileExist(THEME:GetCurrentThemeDirectory().."Fonts/Stream BPM "..name..".ini")
  notice[#notice+1]=LoadFont(hasFont and "Stream BPM "..name or "Common Normal")..{
   Name=name,InitCommand=function(self) self:halign(0):zoom(0.65):diffuse(1,1,1,1):shadowlength(0) end,
  }
 end
 af[#af+1]=notice
end
for i=1,config.max_active_arrows do
 local index=i
 af[#af+1]=Def.ActorFrame{
  Name="GiftBubble"..index,
  InitCommand=function(self) bubbleActors[index]=self self:visible(false) end,
  Def.Quad{Name="Leader",InitCommand=function(self) self:diffuse(1,1,1,1) end},
  Def.Quad{Name="Target",InitCommand=function(self) self:zoomto(3,3):diffuse(1,1,1,1) end},
  Def.ActorMultiVertex{Name="Background",InitCommand=function(self)
   local vertices=roundedBubbleVertices(66,32,4)
   self:SetDrawState({Mode="DrawMode_Fan"}):SetNumVertices(#vertices):SetVertices(vertices)
  end},
  LoadFont(nameFont)..{Name="Sender",InitCommand=function(self) self:zoom(bubbleZoom):vertspacing(-3):diffuse(0,0,0,1):shadowlength(0) end},
 }
end
return af
