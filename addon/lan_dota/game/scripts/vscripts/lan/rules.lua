-- Conventional game options adapted from AI Fun events.lua / gamemode.lua.
local M={}
function M.start(e)
 local o=e.room.options;local mode=e.mode
 GameRules:SetCustomGameTeamMaxPlayers(2,o.radiant_player_number)
 GameRules:SetCustomGameTeamMaxPlayers(3,o.dire_player_number)
 if mode.SetModifyExperienceFilter then mode:SetModifyExperienceFilter(function(_,v)
  local side=PlayerResource:GetTeam(v.player_id_const)==3 and 'dire' or 'radiant'
  if v.experience and v.experience>0 then v.experience=math.floor(v.experience*o[side..'_xp_multiplier']) end
  return true
 end,e) end
 if o.max_level~=30 and mode.SetCustomHeroMaxLevel then
  local xp={0,230,600,1080,1660,2260,2980,3730,4510,5320,6160,7030,7930,9155,10405,11680,12980,14305,15805,17395,18995,20845,22945,25295,27895,31395,35895,41395,47895,55395}
  for i=31,o.max_level do xp[i]=xp[i-1]+i*1000 end
  mode:SetUseCustomHeroLevels(true);GameRules:SetUseCustomHeroXPValues(true)
  mode:SetCustomHeroMaxLevel(o.max_level);mode:SetCustomXPRequiredToReachNextLevel(xp)
 end
 if LinkLuaModifier then
  for _,name in ipairs({'modifier_tower_power','modifier_tower_endure','modifier_bot_protection'}) do LinkLuaModifier(name,'lan/original_modifiers',LUA_MODIFIER_MOTION_NONE) end
 end
 if ListenToGameEvent then ListenToGameEvent('entity_killed',function(k)
  local h=EntIndexToHScript(k.entindex_killed)
  if h and h.IsRealHero and h:IsRealHero() then
   if o.respawn_time_percentage~=100 then h:SetTimeUntilRespawn(math.max(0,h:GetRespawnTime()*o.respawn_time_percentage/100)) end
   h:SetBuybackCooldownTime(o.buyback_cooldown)
  end
 end,nil) end
end
function M.tick(e,phase)
 if phase~='pregame' and phase~='playing' then return end
 local o=e.room.options
 if not Entities then return end
 for _,h in pairs(HeroList:GetAllHeroes()) do
  if h:IsRealHero() and not h:IsIllusion() and not h:IsClone() and not h:IsTempestDouble() and not h.lan_initialized then
   h.lan_initialized=true
   local bat_ok,bat=pcall(h.GetBaseAttackTime,h,false)
   if bat_ok then h.lan_initial_bat=bat else e:emit('BAT_INIT_WARNING',tostring(bat)) end
   local side=h:GetTeamNumber()==3 and 'dire' or 'radiant'
   h:SetGold(0,true);h:SetGold(o[side..'_gold_start'],false)
   while h:GetLevel()<math.min(o[side..'_lvl_start'],o.max_level) do h:HeroLevelUp(false) end
   if o.bot_protection==1 and PlayerResource:IsFakeClient(h:GetPlayerOwnerID()) then h:AddNewModifier(h,nil,'modifier_bot_protection',{}) end
  end
 end
 if not e.buildings_applied then
  e.buildings_applied=true
  for _,class in ipairs({'npc_dota_tower','npc_dota_barracks','npc_dota_fort','npc_dota_filler'}) do
   for _,b in pairs(Entities:FindAllByClassname(class)) do
    if class=='npc_dota_tower' and o.tower_power>1 then b:AddNewModifier(b,nil,'modifier_tower_power',{}):SetStackCount(o.tower_power) end
    if o.tower_endure>1 then b:AddNewModifier(b,nil,'modifier_tower_endure',{}):SetStackCount(o.tower_endure) end
   end
  end
 end
end
return M
