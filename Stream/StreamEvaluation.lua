-- Compact transparent results, shown in both the player and stream columns.
local json=dofile(THEME:GetCurrentThemeDirectory()..'BGAnimations/ScreenGameplay overlay/GiftAPI.Json.lua')
local player=GAMESTATE:GetMasterPlayerNumber()
local stats=STATSMAN:GetCurStageStats():GetPlayerStageStats(player)
local song=GAMESTATE:GetCurrentSong()
local types={'W1','W2','W3','W4','W5','Miss'}
local labels={'FANTASTIC','EXCELLENT','GREAT','DECENT','WAY OFF','MISS'}
local counts={}
for i,key in ipairs(types) do counts[key]=stats:GetTapNoteScores('TapNoteScore_'..key) end
local packet={}
local f=RageFileUtil.CreateRageFile()
if f:Open('Save/GiftAPI/status.json',1) then
 local ok,value=pcall(json.decode,f:Read(8388608))
 if ok and type(value)=='table' then packet=value end
 f:Close()
end
f:destroy()
packet.protocol_version=5 packet.ready=false packet.screen='evaluation'
packet.song_title=song and song:GetDisplayMainTitle() or ''
packet.song_artist=song and song:GetDisplayArtist() or ''
packet.evaluation={grade=stats:GetGrade(),score=stats:GetScore(),
 percent=stats:GetPercentDancePoints(),judgments=counts}
local function publish(visible)
 packet.evaluation_visible=visible packet.reason=visible and 'Evaluation screen' or 'Evaluation ended'
 local file=RageFileUtil.CreateRageFile()
 if file:Open('Save/GiftAPI/status.json',6) then file:Write(json.encode(packet)) file:Close() end
 file:destroy()
end
local af=Def.ActorFrame{
 Name='StreamEvaluation',
 OnCommand=function(self)
  -- Keep only our transparent overlay. Hide the theme header, avatar,
  -- background and CLEARED/FAILED transition without changing navigation.
  for name,actor in pairs(SCREENMAN:GetTopScreen():GetChildren()) do
   if name~='Overlay' then actor:visible(false) end
  end
  PROFILEMAN:SaveMachineProfile()
  publish(true)
  local last=GetTimeSinceStart()
  self:SetUpdateFunction(function()
   local now=GetTimeSinceStart()
   if now-last>=0.1 then publish(true) last=now end
  end)
 end,
 OffCommand=function(self) self:SetUpdateFunction(nil) publish(false) end,
}
-- Preserve score/stat storage and keyboard restart support from Simply Love.
af[#af+1]=LoadActor('./Shared/GlobalStorage.lua')
af[#af+1]=LoadActor('./Shared/ExitHandler.lua')
for _,pn in ipairs(GAMESTATE:GetHumanPlayers()) do af[#af+1]=LoadActor('./PerPlayer/Storage.lua',pn) end
for _,position in ipairs({0.25,0.72}) do
 local x=position
 local card=Def.ActorFrame{InitCommand=function(self) self:xy(SCREEN_WIDTH*x,72) end}
 card[#card+1]=LoadActor(THEME:GetPathG('','_grades/'..stats:GetGrade()..'.lua'),stats)..{
  OnCommand=function(self) self:xy(-82,6):zoom(0.27) end,
 }
 card[#card+1]=LoadFont('Common Normal')..{
  Text='SCORE',InitCommand=function(self) self:xy(80,-10):halign(1):zoom(0.75):strokecolor(0,0,0,1):shadowlength(0) end,
 }
 card[#card+1]=LoadFont('Wendy/_wendy white')..{
  Text=FormatPercentScore(stats:GetPercentDancePoints()),
  InitCommand=function(self) self:xy(100,13):halign(1):zoom(0.4):strokecolor(0,0,0,1):shadowlength(0) end,
 }
 for i,key in ipairs(types) do
  local index=i local tint=SL.JudgmentColors[SL.Global.GameMode][i]
  card[#card+1]=LoadFont('Common Normal')..{
   Text=labels[i],InitCommand=function(self) self:xy(14,58+(index-1)*28):halign(1):zoom(0.9):diffuse(tint):strokecolor(0,0,0,1):shadowlength(0) end,
  }
  card[#card+1]=LoadFont('Wendy/_ScreenEvaluation numbers')..{
   Text=string.format('%04d',counts[key]),
   InitCommand=function(self) self:xy(104,58+(index-1)*28):halign(1):zoom(0.42):diffuse(tint):strokecolor(0,0,0,1):shadowlength(0) end,
  }
 end
 af[#af+1]=card
end
return af
