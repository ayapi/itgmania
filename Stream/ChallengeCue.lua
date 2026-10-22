-- Native PNG challenge design, shared by the player and stream render copy.
local get=...
local base=THEME:GetCurrentThemeDirectory()..'BGAnimations/ScreenGameplay overlay/'
if base:sub(1,1)~='/' then base='/'..base end
local design=dofile(base..'ChallengeDesign.lua')
local present=dofile(base..'ChallengePresentation.lua')
local assets=base..'ChallengeAssets/'
local font=FILEMAN:DoesFileExist(THEME:GetCurrentThemeDirectory()..'Fonts/Stream Noto Sans JP.ini') and 'Stream Noto Sans JP' or 'Common Normal'
local counterFont='Stream Challenge Counter'
local deltaFont='Stream Challenge Delta'
local seenNotice,seenCount,seenClear
local S=design.scale
local MW,MS=224,224/2048
local function number(n)
 return string.format('%.1f',n or 0):gsub('%.0$','')
end
local function fitted(text,value,scale,width)
 text:settext(value):zoom(scale)
 if text:GetZoomedWidth()>width then text:zoom(scale*width/text:GetZoomedWidth()) end
end
local function clipped(text,value)
 text:settext(value):zoom(0.65)
 while value~='' and text:GetZoomedWidth()>235 do
  value=value:gsub('[%z\1-\127\194-\244][\128-\191]*$','')
  text:settext(value..'…')
 end
end
local function image(name,file,x,y,w,h)
 return Def.Sprite{Name=name,Texture=assets..file,
  InitCommand=function(self) self:xy(x,y):zoomto(w,h):visible(false) end}
end
local function countdownImage(name,key)
 local a=design.countdown[key]
 return image(name,a.file,(a.x+a.w/2)*S,(a.y+a.h/2)*S,a.w*S,a.h*S)
end
local function titleState(frame,source,clear)
 local strong=source.kind=='strong'
 local rise=source.rise or 10
 frame:GetChild('Full21'):visible(not clear and strong and rise==21)
 frame:GetChild('Cleared'):visible(clear)
 local prefix=frame:GetChild('Prefix')
 local delta=frame:GetChild('Delta')
 local custom=not clear and not(strong and rise==21)
 prefix:visible(custom) delta:visible(custom)
 if custom then
  local crop=strong and 0 or 1-830/1398
  local width=strong and 174 or 174*(830/1398)
  delta:settext('+'..rise):zoom(0.6)
  local dw=delta:GetZoomedWidth()
  local total=width+dw+3
  prefix:cropright(crop):x(-total/2)
  delta:x(total/2):halign(1)
 end
 for _,skin in ipairs({'attack','cleared'}) do
  for _,side in ipairs({'left','right'}) do
   frame:GetChild(skin..'_'..side):visible((skin=='cleared')==clear)
  end
 end
end
local af=Def.ActorFrame{
 Name='StreamChallengeCue',
 OnCommand=function(self)
  -- Warm the PNG/font draw paths during screen setup, before music starts.
  local warmup=self:GetChild('FontWarmup')
  if warmup then
   local started=GetTimeSinceStart()
   warmup:visible(true):Draw():visible(false)
   Trace(string.format('ChallengeCue design warmup: %.1f ms',(GetTimeSinceStart()-started)*1000))
  end
  self:SetUpdateFunction(function()
   local st,beat,x,ready=get()
   self:visible(st~=nil and ready)
   if not st or not ready then return end
   self:xy(x,design.anchor_y)
   local p=present(st,beat)
   local waiting=p.mode=='waiting' or p.mode=='digit'
   local cleared=p.mode=='cleared'
   local active=p.mode=='meter' or cleared
   local title=self:GetChild('Title')
   title:visible(waiting or active):diffusealpha(cleared and p.alpha or 1)
   if waiting or active then titleState(title,p.source,cleared) end
   self:GetChild('Box'):visible(waiting)
   self:GetChild('Label'):visible(waiting):settext(waiting and ('開始まで'..p.remaining..'小節') or '')
   for i=1,4 do self:GetChild('Number'..i):visible(p.digit==tostring(i)) end
   self:GetChild('Start'):visible(p.mode=='start')
   if st.announcement then
    local a=st.announcement
    if seenNotice~=a.id then seenNotice=a.id self:GetChild('NoticeSound'):play() end
    if p.mode=='digit' then
     local key=a.id..':'..p.digit
     if seenCount~=key then seenCount=key self:GetChild('TickSound'):play() end
    end
   end
   if cleared and seenClear~=p.source.beat then seenClear=p.source.beat self:GetChild('ClearSound'):play() end
   local meter=self:GetChild('Meter')
   meter:visible(active):diffusealpha(cleared and p.alpha or 1)
   if active then
    local t=p.source
    local ratio=p.ratio
    for _,skin in ipairs({'attack','cleared'}) do
     local layer=meter:GetChild(skin)
     layer:visible((skin=='cleared')==cleared)
     -- Crop the full-size image; segment widths never stretch with progress.
     layer:GetChild('Fill'):cropright(1-(72+1908*ratio)/2048)
    end
    meter:GetChild('Cursor'):visible(ratio>0):x((-1024+72+1908*ratio)*MS+(128-127)*MS)
    local value=cleared and t.required_points or t.points
    fitted(meter:GetChild('Counter'),number(value)..' / '..number(t.required_points),0.55,380*MS)
   end
   local source=st.announcement or st.trial
   local sender=self:GetChild('Sender')
   sender:visible(source~=nil and source.kind=='strong' and not cleared and p.mode~='start')
   if source then clipped(sender,source.sender or '') end
   local phase=self:GetChild('Phase')
   phase:visible(p.mode=='meter')
   if p.mode=='meter' then
    local t=p.source
    phase:settext(not t.hearts_enabled and 'ハート無効中 / 救済ギフト・SAFE SHIELDは有効' or
     (t.heart_pending>0 and ('ハート反映待ち '..number(t.heart_pending)..'pt') or ''))
   end
  end)
 end,
 Def.ActorFrame{
  Name='Title',InitCommand=function(self) self:xy(10*S,-71*S):visible(false) end,
  image('Full21','titles/attack_full.png',0,0,205,205*184/1648),
  image('Cleared','titles/cleared.png',0,0,205,205*184/1565),
  Def.Sprite{Name='Prefix',Texture=assets..'titles/attack.png',InitCommand=function(self) self:halign(0):zoomto(174,174*184/1398):visible(false) end},
  LoadFont(deltaFont)..{Name='Delta',InitCommand=function(self) self:y(-6):diffuse(color('#ff953e')):strokecolor(color('#ff692e')):shadowlength(0):visible(false) end},
  image('attack_left','attack/badge_left.png',-10*S-352*S,0,18,18*160/165),
  image('attack_right','attack/badge_right.png',-10*S+370*S,0,18,18*160/155),
  image('cleared_left','cleared/badge_left.png',-10*S-352*S,0,19,19*190/180),
  image('cleared_right','cleared/badge_right.png',-10*S+370*S,0,20,19),
 },
 countdownImage('Box','box'),
 LoadFont(font)..{Name='Label',InitCommand=function(self) self:zoom(0.58):diffuse(color('#fff3c1')):strokecolor(0,0,0,0):shadowlength(0):visible(false) end},
 countdownImage('Number1','1'),countdownImage('Number2','2'),countdownImage('Number3','3'),countdownImage('Number4','4'),
 countdownImage('Start','start'),
 LoadFont(font)..{Name='Sender',InitCommand=function(self) self:y(29):zoom(0.65):visible(false):diffuse(1,1,1,1):strokecolor(0,0,0,1):shadowlength(0) end},
 LoadFont(font)..{Name='Phase',InitCommand=function(self) self:y(43):zoom(0.5):visible(false):diffuse(color('#ffe39b')):strokecolor(0,0,0,1):shadowlength(0) end},
 Def.Sound{Name='NoticeSound',File='./ChallengeNotice.wav'},
 Def.Sound{Name='TickSound',File='./ChallengeTick.wav'},
 Def.Sound{Name='ClearSound',File='./ChallengeClear.wav'},
}
local meter=Def.ActorFrame{Name='Meter',InitCommand=function(self) self:visible(false) end}
for _,skin in ipairs({'attack','cleared'}) do
 local layer=Def.ActorFrame{Name=skin,InitCommand=function(self) self:visible(false) end}
 for _,name in ipairs({'Track','Fill','Frame'}) do
  layer[#layer+1]=Def.Sprite{Name=name,Texture=assets..skin..'/'..name:lower()..'.png',InitCommand=function(self) self:zoomto(MW,256*MS) end}
 end
 layer[#layer+1]=Def.Sprite{Texture=assets..skin..'/chevron_left.png',InitCommand=function(self) self:x(-MW/2-13):zoomto(20,22) end}
 layer[#layer+1]=Def.Sprite{Texture=assets..skin..'/chevron_right.png',InitCommand=function(self) self:x(MW/2+13):zoomto(20,22) end}
 meter[#meter+1]=layer
end
meter[#meter+1]=Def.Sprite{Name='Cursor',Texture=assets..'shared/cursor.png',InitCommand=function(self) self:y((127-128+192-195)*MS):zoomto(256*MS,384*MS) end}
meter[#meter+1]=LoadFont(counterFont)..{Name='Counter',InitCommand=function(self) self:xy((1950-1024)*MS,-1):halign(1):zoom(0.55):diffuse(color('#bbffff')):shadowlength(0) end}
af[#af+1]=meter
if SupportsRenderToTexture() then
 local warm=Def.ActorFrameTexture{Name='FontWarmup',InitCommand=function(self) self:SetWidth(256):SetHeight(64):EnableAlphaBuffer(true):Create():visible(false) end}
 for _,f in ipairs({font,counterFont,deltaFont}) do
  warm[#warm+1]=LoadFont(f)..{Text=f==font and '0123456789 + / 開始まで小節 ハート反映待ち無効中 救済ギフト・SAFE SHIELDは有効 テスト視聴者' or '0123456789 + / .',InitCommand=function(self) self:xy(128,32):zoom(0.7):strokecolor(0,0,0,1):shadowlength(0) end}
 end
 -- Preload normal-alpha PNG draw paths too, without an onscreen flash.
 warm[#warm+1]=Def.Sprite{Texture=assets..'titles/attack_full.png',InitCommand=function(self) self:xy(128,32):zoomto(205,23) end}
 af[#af+1]=warm
end
return af
