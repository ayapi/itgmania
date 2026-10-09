-- ITGmania streaming fork / Simply Love. All gameplay mutations run on the game thread.
local json = dofile(THEME:GetCurrentThemeDirectory().."BGAnimations/ScreenGameplay overlay/GiftAPI.Json.lua")
local directory = "Save/GiftAPI/"
local config = {max_active_arrows=24, max_queued_arrows=512, max_tempo_effects=128,
                min_rate=0.25, max_rate=3, sixteenth_backlog_threshold=48, min_lead_seconds=0.8}
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
 if not contents then return nil end
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
config.sixteenth_backlog_threshold=math.max(1,math.floor(config.sixteenth_backlog_threshold))

local state={session="", server_id="", cursor=0, effects={}, queue={}, active={}, results={}, players={}}
local byname, containers, bubbleActors={}, {}, {}
local song, baseline, originalHaste, lastRate, lastPoll, lastStatus
local reason, stopped, initialized="Starting gameplay",false,false
local currentBpm, totalDelta, effectiveRate=0,0,1
local resultById={}
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
 while #state.results>512 do
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
 local originalTotal,originalJudged,holds=0,0,0
 for _,p in pairs(byname) do
  for key in pairs(p.original or {}) do originalTotal=originalTotal+1 if p.processed[key] then originalJudged=originalJudged+1 end end
  for _,note in ipairs(p.originalData or {}) do if note.length and note.length>0 then holds=holds+1 end end
 end
 write(directory.."status.json",{ready=ready,reason=message or "",session=state.session,
  server_id=state.server_id,cursor=state.cursor,players=state.players,results=state.results,
  song=song and song:GetDisplayMainTitle() or "", base_bpm=currentBpm,
  bpm_delta=totalDelta, effective_bpm=currentBpm*effectiveRate, rate=effectiveRate,
  active_arrows=activeCount(), queued_arrows=queueCount(), tempo_effects=#state.effects,
  original_notes=originalTotal, judged_original_notes=originalJudged,
  hold_intervals=holds,
  performance=performance,
  song_beat=GAMESTATE:GetSongPosition():GetSongBeat(),
  music_seconds=GAMESTATE:GetSongPosition():GetMusicSeconds(),
  saturated=effectiveRate==config.min_rate or effectiveRate==config.max_rate})
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
  for _,note in ipairs(p.tracked) do p.original[noteKey(note[1],note[2])]=true end
  state.players[#state.players+1]=name
 end
 baseline=songOptions("ModsLevel_Current"):MusicRate()
 originalHaste=songOptions("ModsLevel_Current"):Haste()
 if originalHaste~=0 then reason="Turn off Haste before using GiftAPI" return false end
 state.session=tostring(GetTimeSinceStart()).."-"..tostring(math.random(1,100000000))
 state.effects={} state.queue={} state.active={} state.results={} resultById={}
 state.cursor=0 state.server_id=""
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
   elseif command.kind=="tempo" then
    if #state.effects>=config.max_tempo_effects then
     result(command,"rejected","Too many tempo effects")
    else
     modified()
     state.effects[#state.effects+1]={delta=command.bpm_delta,expires=now+command.duration_seconds,event_id=command.event_id}
     result(command,"active")
    end
   elseif command.kind=="notes" then
    if not byname[command.player] then result(command,"rejected","Player is unavailable")
    elseif queueCount()+command.count>config.max_queued_arrows then result(command,"rejected","Arrow queue is full")
    else
     modified()
     command.remaining=command.count command.inserted=0
     state.queue[#state.queue+1]=command
     result(command,"queued")
    end
   else result(command,"rejected","Unknown command") end
  end
 end
end
local function updateTempo(now)
 totalDelta=0
 for i=#state.effects,1,-1 do
  local effect=state.effects[i]
  if now>=effect.expires then
   local r=resultById[effect.event_id]
   if r then r.state="expired" end
   table.remove(state.effects,i)
  else totalDelta=totalDelta+effect.delta end
 end
 local master=byname[ToEnumShortString(GAMESTATE:GetMasterPlayerNumber())]
 if not master then return end
 local beat=master.ps:GetSongPosition():GetSongBeat()
 currentBpm=master.timing:GetBPMAtBeat(beat)
 if currentBpm>0 then
  local rate=baseline+totalDelta/currentBpm
  rate=math.max(config.min_rate,math.min(config.max_rate,rate))
  applyRate(rate)
 end
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
 return backlog>=config.sixteenth_backlog_threshold and 0.25 or 0.5
end
local function slot(p,index,grid)
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
    if not occupied[col] then
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
 if #state.queue==0 or activeCount()>=config.max_active_arrows then return end
 local command=state.queue[1]
 local p=byname[command.player]
 local data=p.actor:GetNoteData()
 local index=occupancyIndex(data)
 local added={}
 local grid=giftGrid(queueCount())
 while command.remaining>0 and #added<4 and activeCount()+#added<config.max_active_arrows do
  local beat,col=slot(p,index,grid)
  if not beat then
   local r=resultById[command.event_id]
   if r then r.state="partial" r.reason="No room before the end of the chart" end
   table.remove(state.queue,1) break
  end
  data[#data+1]={beat,col,"TapNoteType_Tap",grid==0.5 and "TapNote_8th" or "TapNote_16th"}
  local row=math.floor(beat*48+0.5)
  index.rows[row]=index.rows[row] or {occupied={},feet={}}
  index.rows[row].occupied[col]=true index.rows[row].feet[col]=true
  added[#added+1]={beat=beat,column=col,player=command.player,sender=command.sender,event_id=command.event_id,done=false}
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
  for _,note in ipairs(added) do state.active[#state.active+1]=note end
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
  local half=40*math.abs(p.actor:GetZoomX()*(p.field and p.field:GetZoomX() or 1))
  for col=1,4 do
   local x=screenPosition(p,beat,col)
   left=math.min(left,x-half) right=math.max(right,x+half)
  end
 end
 return left-12,right+12
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
local function labelSlot(occupied,desired)
 -- Let a label enter partly clipped with its arrow. Keeping the whole
 -- box inside the bottom edge would bake in a permanent upward offset.
 local low,high=-30,SCREEN_HEIGHT+30
 for step=0,math.ceil(SCREEN_HEIGHT/46) do
  for _,sign in ipairs({1,-1}) do
   local y=desired+step*46*sign
   if y>=low and y<=high then
    local free=true
    for _,other in ipairs(occupied) do if math.abs(y-other)<45 then free=false break end end
    if free then occupied[#occupied+1]=y return y end
   end
  end
 end
end
local function labelPosition(note,occupied,arrowY,right)
 if note.labelOffset==nil then
  if SCREEN_WIDTH-right-8<66 then return end
  local y=labelSlot(occupied,arrowY)
  if not y then return end
  -- Allocate once. A departing neighbour, a new gift, or a screen edge
  -- must never cause an existing name to jump to another slot.
  note.labelOffset=y-arrowY
  note.labelEdge=right
 end
 return arrowY+note.labelOffset,note.labelEdge
end
local function updateBubbles()
 local used,visible={},{}
 local _,right=railBounds()
 local occupied={}
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
     if py>=0 and py<=SCREEN_HEIGHT and alpha>0 then
      visible[#visible+1]={note=note,actor=a,p=p,x=px,y=py}
     end
    end
   end
  end
 end
 table.sort(visible,function(a,b) if a.y==b.y then return a.note.column<b.note.column end return a.y<b.y end)
 -- Reserve established labels before allocating space for new arrivals.
 for _,item in ipairs(visible) do
  if item.note.labelOffset~=nil then occupied[#occupied+1]=item.y+item.note.labelOffset end
 end
 for _,item in ipairs(visible) do
  -- A single rail on the right keeps the stream crop narrow. All gifters
  -- keep the same label size; never spill labels onto the left or notes.
  local width=66
  local y,edge=labelPosition(item.note,occupied,item.y,right)
  if y then
   local x=edge+width/2
   local half=25*math.abs(item.p.actor:GetZoomX()*(item.p.field and item.p.field:GetZoomX() or 1))
   local targetX=item.x+half
   local dx,dy=targetX-edge,item.y-y
   local angle=math.atan2(dy,dx)*180/math.pi
   local a=item.actor
   a:xy(x,y):visible(true)
   a:GetChild("Background"):zoomto(width,40)
   local text=a:GetChild("Sender")
   if not item.note.formattedName then
    text:maxwidth(0)
    item.note.formattedName=formatSender(item.note.sender,function(value)
     text:settext(value)
     return text:GetWidth()*0.7
    end,width-10)
   end
   text:settext(item.note.formattedName):maxwidth((width-10)/0.7)
   a:GetChild("Leader"):xy((edge+targetX)/2-x,dy/2):zoomto(math.sqrt(dx*dx+dy*dy),1):rotationz(angle)
   a:GetChild("Target"):xy(targetX-x,item.y-y)
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
  if r.state=="queued" or r.state=="active" then r.state="discarded" r.reason=message end
 end
 state.active={} state.queue={} state.effects={}
 totalDelta=0
 resetRate()
 stopped=true
 snapshot(false,message)
end
local af=Def.ActorFrame{
 Name="SimplyLoveGiftAPI",
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
    if ready and now-lastPoll>=0.1 then measured("max_commands_ms",function() consume(now) end) lastPoll=now end
    if ready then
     local started=GetTimeSinceStart()
     insertNotes()
     performance.max_insert_ms=math.max(performance.max_insert_ms,(GetTimeSinceStart()-started)*1000)
    end
    measured("max_tempo_ms",function() updateTempo(now) end)
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
for i=1,config.max_active_arrows do
 local index=i
 af[#af+1]=Def.ActorFrame{
  InitCommand=function(self) bubbleActors[index]=self self:visible(false) end,
  Def.Quad{Name="Leader",InitCommand=function(self) self:diffuse(1,1,1,1) end},
  Def.Quad{Name="Target",InitCommand=function(self) self:zoomto(3,3):diffuse(1,1,1,1) end},
  Def.Quad{Name="Background",InitCommand=function(self) self:zoomto(66,40):diffuse(1,1,1,1) end},
  LoadFont("Common Normal")..{Name="Sender",InitCommand=function(self) self:zoom(0.7):maxwidth(80):diffuse(0,0,0,1):shadowlength(0) end},
 }
end
return af
