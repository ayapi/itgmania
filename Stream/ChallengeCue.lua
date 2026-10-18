-- Native player-side warning/countdown/clear, plus one set of game cue sounds.
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
  self:SetUpdateFunction(function()
   local st,beat,x,ready=get()
   local label=self:GetChild('Label') local sender=self:GetChild('Sender')
   if not st or not ready then label:visible(false) sender:visible(false) return end
   self:x(x):y(220)
   local a,r=st.announcement,st.resolution
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
   end
   label:visible(text~=''):settext(text):zoom(scale):diffuse(tint)
   if label:GetZoomedWidth()>235 then label:zoom(scale*235/label:GetZoomedWidth()) end
   sender:visible(not r and a~=nil and a.kind=='strong')
   if a and a.kind=='strong' then
    clipped(a.sender or '',sender)
   end
  end)
 end,
 LoadFont(font)..{Name='Label',InitCommand=function(self) self:visible(false):strokecolor(0,0,0,1):shadowlength(0) end},
 LoadFont(font)..{Name='Sender',InitCommand=function(self) self:y(-18):visible(false):diffuse(1,1,1,1):strokecolor(0,0,0,1):shadowlength(0) end},
 Def.Sound{Name='NoticeSound',File='./ChallengeNotice.wav'},
 Def.Sound{Name='TickSound',File='./ChallengeTick.wav'},
 Def.Sound{Name='ClearSound',File='./ChallengeClear.wav'},
}
return af
