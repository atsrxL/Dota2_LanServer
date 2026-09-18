-- Standard dota map: retain only the two river powerup spawners.
local M={}
function M.allow(k)
 local id=tonumber(k.spawner_entindex_const)
 local spawner=id and EntIndexToHScript(id) or nil
 return spawner~=nil and spawner:GetClassname()=='dota_item_rune_spawner_powerup'
end
function M.init(e)
 if e.mode.SetUseDefaultDOTARuneSpawnLogic then e.mode:SetUseDefaultDOTARuneSpawnLogic(true) end
 if not e.mode.SetRuneSpawnFilter then return end
 local seen={}
 e.mode:SetRuneSpawnFilter(function(_,k)
  local allowed=M.allow(k)
  local key=tostring(k.spawner_entindex_const)
  if not seen[key] then
   seen[key]=true
   local spawner=EntIndexToHScript(tonumber(k.spawner_entindex_const) or -1)
   e:emit('RUNE_FILTER',{spawner=key,class=spawner and spawner:GetClassname() or 'unknown',allowed=allowed})
  end
  return allowed
 end,e)
end
return M
