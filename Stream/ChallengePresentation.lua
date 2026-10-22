-- Pure musical-clock presentation; supplied layout's one-beat measure flashes.
return function(st,beat)
 local r,a,t=st.resolution,st.announcement,st.trial
 if r and r.resolved and beat<r.end_beat then
  return {mode='cleared',source=r,ratio=1,alpha=math.min(1,(r.end_beat-beat)*5)}
 end
 if a then
  local boundaries=a.measure_boundaries or {}
  for i=1,#boundaries-1 do
   if beat>=boundaries[i]-0.000001 and beat<boundaries[i+1]-0.000001 then
    local remaining=#boundaries-i
    local digit=remaining<=4 and beat-boundaries[i]<1
    return {mode=digit and 'digit' or 'waiting',digit=digit and tostring(remaining) or nil,
     remaining=remaining,source=a}
   end
  end
  return {mode='waiting',remaining=a.remaining_measures,source=a}
 end
 if t then
  if t.start_beat and beat>=t.start_beat and beat<t.start_beat+1 then return {mode='start',source=t} end
  return {mode='meter',source=t,ratio=math.max(0,math.min(1,t.points/math.max(1,t.required_points)))}
 end
 return {mode='hidden'}
end
