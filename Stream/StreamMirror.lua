-- A render-only copy of P1: invert directions and lane order, preserve time.
if not PREFSMAN:GetPreference("StreamerMode") then return Def.Actor{} end
local player, gifts, fade
local warned=false
return Def.ActorFrame{
 Name="StreamMirror",
 OnCommand=function(self)
  self:visible(false)
  self:SetUpdateFunction(function()
   local screen=SCREENMAN:GetTopScreen()
   player=screen:GetChild("PlayerP1")
   local style=GAMESTATE:GetCurrentStyle()
   if not player or not player.DrawStreamMirror or GAMESTATE:IsPlayerEnabled(PLAYER_2)
      or not style or style:GetStepsType()~="StepsType_Dance_Single" then
    self:visible(false)
    SL.StreamMirrorOffsetX=nil
    SL.StreamMirrorOffsetY=nil
    return
   end
   gifts=self:GetParent():GetChild("SimplyLoveGiftAPI")
   player:x(SCREEN_WIDTH*0.25)
   local offset=SCREEN_WIDTH*0.72-player:GetX()
   -- Mirror horizontally only: both receptor rows stay at the same height.
   self:xy(offset,0):visible(true)
   SL.StreamMirrorOffsetX=offset
   SL.StreamMirrorOffsetY=0
  end)
  self:SetDrawFunction(function()
   if not player then return end
   local ok,error=pcall(function()
    player:DrawStreamMirror()
    -- Fade only the already-rendered notes. Stationary cards and BPM
    -- must stay opaque even when their top slots occupy this region.
    if fade then fade:xy(player:GetX(),32):Draw() end
    if gifts then gifts:playcommand("StreamMirrorDraw") end
   end)
   if not ok then
    if not warned then Trace("StreamMirror: "..tostring(error)) warned=true end
    self:visible(false)
   end
  end)
 end,
 OffCommand=function(self)
  self:SetUpdateFunction(nil)
  SL.StreamMirrorOffsetX=nil
  SL.StreamMirrorOffsetY=nil
 end,
 Def.Quad{
  Name="StreamMirrorNoteFade",
  InitCommand=function(self)
   fade=self
   self:zoomto(SCREEN_WIDTH/2,64):blend("BlendMode_AlphaKnockOut")
       :diffusetopedge(1,1,1,1):diffusebottomedge(1,1,1,0)
  end,
 },
}
