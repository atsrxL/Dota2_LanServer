-- Shuffle a private copy of the verified Tiandixing hero pool once per match.
local M={}
function M.draft(supported,used,random)
 if type(supported)~='table' or #supported==0 then error('verified_bot_hero_pool_missing') end
 local pool,seen={},{}
 for _,hero in ipairs(supported) do
  if type(hero)~='string' or not hero:match('^[a-z0-9_]+$') then error('invalid_bot_hero_pool') end
  if not seen[hero] and not used['npc_dota_hero_'..hero] then pool[#pool+1]=hero end
  seen[hero]=true
 end
 for i=#pool,2,-1 do
  local j=random(1,i)
  pool[i],pool[j]=pool[j],pool[i]
 end
 return pool
end
return M
