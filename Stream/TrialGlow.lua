-- Stream-only edge glow, behind notes; beat pulse never exceeds 3 Hz.
local af=Def.ActorFrame{
 OnCommand=function(self)
  self:SetUpdateFunction(function()
   local t=SL.StreamTrial self:visible(t~=nil)
   if not t then return end
   local skip=math.max(1,math.ceil(t.bpm/180))
   local phase=(t.beat/skip)%1
   self:diffusealpha(0.06+0.07*(1+math.cos(phase*math.pi*2))/2)
  end)
 end,
}
for _,x in ipairs({_screen.w*0.25,_screen.w*0.72}) do
 for _,sign in ipairs({-1,1}) do
  af[#af+1]=Def.Quad{InitCommand=function(self)
   self:xy(x+sign*128,_screen.cy):zoomto(10,_screen.h):diffuse(1,0.20,0.025,1)
  end}
 end
end
return af
