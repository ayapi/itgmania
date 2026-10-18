-- Native challenge HUD for both player and render-only stream copy.
local get=...
local font=FILEMAN:DoesFileExist(THEME:GetCurrentThemeDirectory()..'Fonts/Stream Noto Sans JP.ini') and 'Stream Noto Sans JP' or 'Common Normal'
local seenNotice,seenCount,seenClear
local function clipped(name,text)
 text:settext(name):zoom(0.65)
 while name~='' and text:GetZoomedWidth()>220 do
  name=name:gsub('[%z\1-\127\194-\244][\128-\191]*$','')
  text:settext(name..'…')
 end
end
local af=Def.ActorFrame{
 Name='StreamChallengeCue',
 OnCommand=function(self)
  -- Loading a font does not exercise its first stroked draw. Render
  -- it once into an undisplayed texture during the pre-song screen setup.
  local warmup=self:GetChild('FontWarmup')
  if warmup then
   local started=GetTimeSinceStart()
   warmup:visible(true):Draw():visible(false)
   Trace(string.format('ChallengeCue font warmup: %.1f ms',(GetTimeSinceStart()-started)*1000))
  end
  self:SetUpdateFunction(function()
   local st,beat,x,ready=get()
   local label=self:GetChild('Label') local sender=self:GetChild('Sender')
   self:visible(st~=nil and ready)
   if not st or not ready then return end
   self:x(x):y(220)
   local a,r,t=st.announcement,st.resolution,st.trial
   local active=t~=nil and r==nil and a==nil
   local meter=self:GetChild('Meter')
   meter:visible(active)
   if active then
    local progress=math.max(0,math.min(1,t.points/math.max(1,t.required_points)))
    meter:GetChild('Fill'):zoomto(216*progress,7):diffuse(color(t.kind=='strong' and '#ff8647' or '#ffbb57'))
    local remaining=string.format('残り %.1fpt',t.remaining_points)
    if t.heart_pending>0 then remaining=remaining..string.format(' / ハート反映待ち %.1fpt',t.heart_pending) end
    meter:GetChild('Remaining'):settext(remaining)
    meter:GetChild('Phase'):settext(not t.hearts_enabled and 'ハート無効中 / 救済ギフト・ロックは有効' or '')
   end
   local text,scale,tint='',0.8,color('#ffe39b')
   if r then
    text='CHALLENGE CLEAR!' scale=0.9 tint=color('#b7fff2')
    if seenClear~=r.beat then seenClear=r.beat self:GetChild('ClearSound'):play() end
    local phase=(beat-r.beat)/(r.end_beat-r.beat)
    scale=scale*(1+0.12*math.exp(-phase*16))
    tint[4]=math.min(1,(1-phase)*5)
   elseif a then
    if seenNotice~=a.id then seenNotice=a.id self:GetChild('NoticeSound'):play() end
    text=(a.kind=='strong' and 'CHALLENGE ATTACK' or 'CHALLENGE')..' まで'..a.remaining_measures..'小節'
    if a.countdown then
     text=tostring(a.countdown) scale=2.3
     local key=a.id..':'..a.countdown
     if seenCount~=key then seenCount=key self:GetChild('TickSound'):play() end
     scale=scale*(1+0.1*math.exp(-(beat-math.floor(beat))*14))
    end
   elseif t then
    text=(t.kind=='strong' and '強い試練 ＋' or 'CHALLENGE ＋')..t.rise
    scale=t.kind=='strong' and 1.05 or 0.9
    tint=color(t.kind=='strong' and '#ff6e40' or '#ffbb57')
   end
   label:visible(text~=''):settext(text):zoom(scale):diffuse(tint)
   if label:GetZoomedWidth()>235 then label:zoom(scale*235/label:GetZoomedWidth()) end
   local source=a or t
   sender:visible(not r and source~=nil and source.kind=='strong')
   if source and source.kind=='strong' then
    clipped(source.sender or '',sender)
   end
  end)
 end,
 LoadFont(font)..{Name='Label',InitCommand=function(self) self:visible(false):strokecolor(0,0,0,1):shadowlength(0) end},
 LoadFont(font)..{Name='Sender',InitCommand=function(self) self:y(-18):visible(false):diffuse(1,1,1,1):strokecolor(0,0,0,1):shadowlength(0) end},
 Def.ActorFrame{
  Name='Meter',InitCommand=function(self) self:visible(false) end,
  Def.Quad{Name='Border',InitCommand=function(self) self:y(18):zoomto(218,9):diffuse(1,1,1,1) end},
  Def.Quad{Name='Background',InitCommand=function(self) self:y(18):zoomto(216,7):diffuse(color('#191919')) end},
  Def.Quad{Name='Fill',InitCommand=function(self) self:xy(-108,18):halign(0):zoomto(0,7) end},
  LoadFont(font)..{Name='Remaining',InitCommand=function(self) self:y(31):zoom(0.6):diffuse(1,1,1,1):strokecolor(0,0,0,1):shadowlength(0) end},
  LoadFont(font)..{Name='Phase',InitCommand=function(self) self:y(44):zoom(0.5):diffuse(color('#ffe39b')):strokecolor(0,0,0,1):shadowlength(0) end},
 },
 Def.Sound{Name='NoticeSound',File='./ChallengeNotice.wav'},
 Def.Sound{Name='TickSound',File='./ChallengeTick.wav'},
 Def.Sound{Name='ClearSound',File='./ChallengeClear.wav'},
}
if SupportsRenderToTexture() then
 af[#af+1]=Def.ActorFrameTexture{
  Name='FontWarmup',
  InitCommand=function(self) self:SetWidth(256):SetHeight(64):EnableAlphaBuffer(true):Create():visible(false) end,
  LoadFont(font)..{
   Text='CHALLENGE ATTACK CLEAR! 0123456789 自動試練 強い試練 ＋ 残り pt / ハート反映待ち 無効中 救済ギフト・ロックは有効 テスト視聴者 ほか人 まで小節',
   InitCommand=function(self) self:xy(128,32):zoom(0.8):diffuse(color('#ffe39b')):strokecolor(0,0,0,1):shadowlength(0) end,
  },
 }
end
return af
