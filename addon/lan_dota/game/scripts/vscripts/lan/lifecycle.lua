-- Personal LAN matches remain alive until the normal Ancient victory condition.
local M={}
function M.init(engine)
    if type(Convars.SetBool)~='function' or type(Convars.SetInt)~='function' then return end
    Convars:SetBool('dota_surrender_on_disconnect',false)
    Convars:SetBool('sv_hibernate_when_empty',false)
    Convars:SetBool('dota_allow_pause_in_match',true)
    -- Do not assume undocumented zero/negative timeout semantics. Use a positive
    -- signed-int maximum (68 years), beyond any supported match lifetime.
    local lifetime=2147483647
    for _,name in ipairs({'dota_auto_surrender_all_disconnected_timeout',
        'dota_pause_force_unpause_time','dota_pause_limit'}) do
        Convars:SetInt(name,lifetime)
    end
    local actual={}
    for _,name in ipairs({'dota_surrender_on_disconnect','sv_hibernate_when_empty',
        'dota_allow_pause_in_match','dota_auto_surrender_all_disconnected_timeout',
        'dota_pause_force_unpause_time','dota_pause_limit'}) do
        if type(Convars.GetStr)=='function' then actual[name]=Convars:GetStr(name) end
    end
    engine:emit('LIFECYCLE',actual)
end
return M
