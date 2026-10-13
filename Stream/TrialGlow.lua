-- Emergency field edges behind notes. One slow quarter-beat pulse, <=3 Hz.
local af=Def.ActorFrame{
 Name="StreamTrialGlow",
 InitCommand=function(self) SL.StreamTrialGlowActor=self self:visible(false) end,
 OnCommand=function(self)
  self:SetUpdateFunction(function()
   local t=SL.StreamTrial self:visible(t~=nil)
   if not t then return end
   local skip=math.max(1,math.ceil(t.bpm/180))
   local phase=(t.beat/skip)%1
   self:diffusealpha(0.26+0.22*(1+math.cos(phase*math.pi*2))/2)
  end)
 end,
 OffCommand=function(self) SL.StreamTrialGlowActor=nil end,
}
for _,x in ipairs({_screen.w*0.25,_screen.w*0.72}) do
 for _,sign in ipairs({-1,1}) do
  af[#af+1]=Def.Quad{InitCommand=function(self)
   self:xy(x+sign*136,_screen.cy):zoomto(14,_screen.h):diffuse(1,0.20,0.025,1)
   -- The bright rim stays outside the arrow silhouettes and fades inward.
   if sign<0 then self:diffuseleftedge(1,0.20,0.025,1):diffuserightedge(1,0.20,0.025,0)
   else self:diffuseleftedge(1,0.20,0.025,0):diffuserightedge(1,0.20,0.025,1) end
  end}
 end
end
return af
