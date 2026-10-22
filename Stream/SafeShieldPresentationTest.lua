local present=dofile(THEME:GetCurrentThemeDirectory()..'BGAnimations/ScreenGameplay overlay/SafeShieldPresentation.lua')
local checks=0
for _,row in ipairs({{10,'10s'},{9.1,'10s'},{9,'9s'},{0.1,'1s'},{999,'999s'}}) do
 local p=present{active=true,remaining_seconds=row[1],viewer_name='テスト視聴者'}
 assert(p.visible and p.time_text==row[2]) checks=checks+1
end
for _,n in ipairs({0,-1,math.huge,0/0,'10'}) do
 local p=present{active=true,remaining_seconds=n}
 assert(not p.visible and p.time_text=='') checks=checks+1
end
assert(not present{active=false,remaining_seconds=10}.visible) checks=checks+1
assert(not present{active=true}.visible) checks=checks+1
assert(present{active=true,remaining_seconds=10,viewer_name=' \r\n名前\n '}.viewer_name=='名前') checks=checks+1
assert(present{active=true,remaining_seconds=10,viewer_name=''}.viewer_name=='') checks=checks+1
return checks
