-- Native SAFE SHIELD replaces the old gold lock badge in both render columns.
local register=...
local base=THEME:GetCurrentThemeDirectory()..'BGAnimations/ScreenGameplay overlay/'
if base:sub(1,1)~='/' then base='/'..base end
local design=dofile(base..'SafeShieldDesign.lua')
local present=dofile(base..'SafeShieldPresentation.lua')
local S=design.scale
local font=FILEMAN:DoesFileExist(THEME:GetCurrentThemeDirectory()..'Fonts/Stream Noto Sans JP.ini') and 'Stream Noto Sans JP' or 'Common Normal'
local fontScale=32*S/16
local lastViewerName
local function nameText(actor,value)
 if value==lastViewerName then return end
 lastViewerName=value
 actor:settext(value):zoom(fontScale)
 while value~='' and actor:GetZoomedWidth()>320*S do
  value=value:gsub('[%z\1-\127\194-\244][\128-\191]*$','')
  actor:settext(value..'…')
 end
end
local af=Def.ActorFrame{
 Name='StreamLock',
 InitCommand=function(self) self:visible(false) register(self) end,
 UpdateShieldCommand=function(self,params)
  local p=present{active=params.active,viewer_name=params.sender,remaining_seconds=params.seconds}
  self:xy(params.x,design.anchor_y):visible(p.visible)
  if not p.visible then return end
  local info=self:GetChild('Info')
  local name=info:GetChild('Sender') local timer=info:GetChild('Time')
  nameText(name,p.viewer_name)
  name:visible(p.viewer_name~='')
  timer:settext(p.time_text):zoom(fontScale)
  if p.viewer_name=='' then
   timer:x(-timer:GetZoomedWidth()/2)
  else
   local width=name:GetZoomedWidth()+10*S+80*S
   name:x(-width/2)
   timer:x(-width/2+name:GetZoomedWidth()+10*S)
  end
 end,
}
for _,key in ipairs({'shield_left','shield_right','title'}) do
 local a=design.assets[key]
 af[#af+1]=Def.Sprite{
  Name=key,Texture=base..'SafeShieldAssets/'..a.file,
  InitCommand=function(self) self:xy((a.x+a.w/2)*S,(a.y+a.h/2)*S):zoomto(a.w*S,a.h*S) end,
 }
end
af[#af+1]=Def.ActorFrame{
 Name='Info',InitCommand=function(self) self:xy(10*S,-5*S) end,
 LoadFont(font)..{Name='Sender',InitCommand=function(self) self:halign(0):zoom(fontScale):diffuse(color('#00fff1')):strokecolor(0,0,0,0):shadowlength(0) end},
 LoadFont(font)..{Name='Time',InitCommand=function(self) self:halign(0):zoom(fontScale):diffuse(color('#00fff1')):strokecolor(0,0,0,0):shadowlength(0) end},
}
return af
