-- AlphaKnockOut preserves destination RGB and multiplies its alpha by
-- (1 - source alpha), so missed notes disappear into real transparency.
if not PREFSMAN:GetPreference("StreamerMode") then return Def.Actor{} end

local height = 64
local mask
local player,feedback
return Def.ActorFrame{
 Name="StreamTopEdgeFade",
 Def.Quad{InitCommand=function(self)
  mask=self
  self:xy(SCREEN_CENTER_X,height/2):zoomto(SCREEN_WIDTH,height)
      :blend("BlendMode_AlphaKnockOut")
      :diffusetopedge(1,1,1,1):diffusebottomedge(1,1,1,0)
 end},
 Def.ActorFrame{
  Name='StreamFeedbackAfterFade',
  InitCommand=function(self)
   feedback=self
   self:SetDrawFunction(function()
    if not player then return end
    for _,name in ipairs({'Combo','Judgment'}) do
     local actor=player:GetChild(name)
     -- Only redraw feedback near the top fade; lower feedback needs no copy.
     if actor and actor:GetY()+player:GetY()<height+40 then actor:Draw() end
    end
   end)
  end,
 },
 OnCommand=function(self)
  SL.StreamFeedbackAfterFade=feedback
  self:SetDrawFunction(function()
   mask:Draw()
   if player then feedback:xy(player:GetX(),player:GetY()):Draw() end
  end)
  self:SetUpdateFunction(function()
   player=SCREENMAN:GetTopScreen():GetChild('PlayerP1')
   -- The mirror fades its notes before drawing its stationary UI.
   local mirrored=SL.StreamMirrorOffsetX~=nil
   mask:x(mirrored and SCREEN_WIDTH/4 or SCREEN_CENTER_X)
       :zoomto(mirrored and SCREEN_WIDTH/2 or SCREEN_WIDTH,height)
  end)
 end,
 OffCommand=function(self) SL.StreamFeedbackAfterFade=nil self:SetUpdateFunction(nil) end,
}
