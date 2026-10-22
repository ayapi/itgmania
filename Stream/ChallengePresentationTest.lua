local p=dofile(THEME:GetCurrentThemeDirectory()..'BGAnimations/ScreenGameplay overlay/ChallengePresentation.lua')
local checks=0
local function eq(a,b) assert(a==b,tostring(a)..' ~= '..tostring(b)) checks=checks+1 end
local a={kind='strong',rise=21,start_beat=96,remaining_measures=4,measure_boundaries={80,84,88,92,96}}
for i=0,3 do
 local beat=80+i*4
 for _,age in ipairs({0,0.2,0.999}) do
  local out=p({announcement=a},beat+age)
  eq(out.mode,'digit') eq(out.digit,tostring(4-i))
 end
 eq(p({announcement=a},beat+1).mode,'waiting')
 eq(p({announcement=a},beat+3.9).mode,'waiting')
end
-- Three-beat measures still flash once at each actual boundary.
a.measure_boundaries={20,23,26};a.start_beat=26
eq(p({announcement=a},20.2).digit,'2')
eq(p({announcement=a},21.1).mode,'waiting')
eq(p({announcement=a},23.2).digit,'1')
local t={start_beat=26,points=20,required_points=80}
eq(p({trial=t},26).mode,'start') eq(p({trial=t},26.999).mode,'start')
eq(p({trial=t},27).mode,'meter') eq(p({trial=t},27).ratio,0.25)
eq(p({trial=t},28).mode,'meter')
-- Seek backwards recomputes from music time; there is no countdown timer.
eq(p({trial=t},26.2).mode,'start')
local r={resolved=true,beat=40,end_beat=42,required_points=80}
eq(p({resolution=r},40).mode,'cleared') eq(p({resolution=r},41.9).ratio,1)
eq(p({resolution=r},42).mode,'hidden') eq(p({},42).mode,'hidden')
return checks
