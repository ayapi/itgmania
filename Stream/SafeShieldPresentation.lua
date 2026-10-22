-- The game owns the timer. Round positive fractional seconds up, never to 0s.
return function(input)
 local n=input.remaining_seconds
 local visible=input.active==true and type(n)=='number' and n==n and n<math.huge and n>0
 local name=type(input.viewer_name)=='string' and input.viewer_name or ''
 name=name:gsub('[\r\n]+',' '):gsub('^%s+',''):gsub('%s+$','')
 return {visible=visible,viewer_name=name,time_text=visible and (math.ceil(n)..'s') or ''}
end
