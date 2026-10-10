-- AlphaKnockOut preserves destination RGB and multiplies its alpha by
-- (1 - source alpha), so missed notes disappear into real transparency.
if not PREFSMAN:GetPreference("StreamerMode") then return Def.Actor{} end

local height = 64
return Def.Quad{
 Name="StreamTopEdgeFade",
 InitCommand=function(self)
  self:xy(SCREEN_CENTER_X,height/2):zoomto(SCREEN_WIDTH,height)
      :blend("BlendMode_AlphaKnockOut")
      :diffusetopedge(1,1,1,1):diffusebottomedge(1,1,1,0)
 end,
}
