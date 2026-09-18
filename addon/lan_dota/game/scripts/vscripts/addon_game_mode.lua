local Engine=require('lan.engine')
local Config=require('lan.generated')
function Precache(context)
    -- Standard dota map/default heroes; no custom models or Valve map copied.
end
function Activate()
    if GameRules.LANLab then
        print('LANLAB|'..Config.session..'|ERROR|script_reload_not_supported; restart_map_process')
        return
    end
    local instance=Engine.new(Config)
    GameRules.LANLab=instance
    local ok,err=pcall(function() instance:init() end)
    if not ok then
        instance.room:fail('initialization_failed')
        instance:emit('ERROR','initialization_failed:'..tostring(err))
    end
end
