-- Resolve the engine callback SOURCE ENTITY, never authorize keys.PlayerID.
local M={}
function M.resolve(source_index, resource, entity_lookup)
    if type(source_index)~='number' or source_index<0 or source_index%1~=0 then return nil end
    local ok,source=pcall(entity_lookup,source_index)
    if not ok or not source then return nil end
    -- Enumeration also handles controllers whose GetPlayerID is temporarily -1.
    -- No fallback from unverified user payload to administrative identity.
    for pid=0,63 do
        local found,player=pcall(function() return resource:GetPlayer(pid) end)
        if found and player and player==source then return pid end
    end
    return nil
end
return M
