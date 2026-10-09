-- Used by the Simply Love streaming hook in Sch-classic-smnote.
-- Convert native white-to-black note dimming into opacity-only fading at
-- draw time. No green overlay, note-data change, or player modifier is used.
local taps={ ["Tap Note"]=true,["Tap Fake"]=true,["Tap Lift"]=true,
             ["Tap Addition"]=true,["Tap Mine"]=true }
return function(actor,element,player)
 if not taps[element] or Var "SpriteOnly" then return actor end
 actor.Name="StreamNote"
 return Def.ActorFrame{
  InitCommand=function(self)
   self:propagate(true)
   self:SetDrawFunction(function(frame)
    -- NoteDisplay sets the outer frame's diffuse for this particular note
    -- immediately before Draw(). Custom drawing does not propagate that
    -- RGB multiplier to the child; use it only as an alpha multiplier.
    local diffuse=frame:GetDiffuse()
    local brightness=math.max(0,math.min(1,diffuse[1],diffuse[2],diffuse[3]))
    local opacity=math.max(0,math.min(1,diffuse[4]*brightness))
    local note=frame:GetChild("StreamNote")
    note:diffuse(1,1,1,opacity)
    if opacity>0 then note:Draw() end
   end)
  end,
  actor,
 }
end
