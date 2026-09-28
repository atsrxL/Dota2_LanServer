-- Match income rules: a shared time ramp plus per-bot triangular death stacks.
local M={}
-- Single source for every income number; engine GOLD_RULE reports these values.
M.RULES={
 ramp_start_seconds=300,  -- base multiplier starts rising at 5:00
 ramp_end_seconds=900,    -- and reaches ramp_max at 15:00
 ramp_max=1.5,
 max_layers=9,            -- bot death stacks: bonus = layers*(layers+1)/20
 kill_reduce_layers=3,    -- a bot hero kill removes this many stacks
 max_multiplier=5,        -- total cap for bots (base + stack bonus)
}
function M.base()
 -- The match clock excludes pregame and stops while paused.
 local r=M.RULES
 local seconds=GameRules:GetDOTATime(false,false)
 local progress=(seconds-r.ramp_start_seconds)/(r.ramp_end_seconds-r.ramp_start_seconds)
 return 1+(r.ramp_max-1)*math.max(0,math.min(1,progress))
end
local function is_bot(pid)
 return type(pid)=='number' and PlayerResource:IsValidPlayerID(pid)
  and PlayerResource.IsFakeClient~=nil and PlayerResource:IsFakeClient(pid)
end
-- Gold and XP share the same stack bonus.
function M.bonus(e,pid)
 if not is_bot(pid) then return 0 end
 local deaths=e.bot_death_bonus and e.bot_death_bonus[pid] or 0
 return deaths*(deaths+1)/20
end
function M.multiplier(e,pid)
 local base=M.base()
 return is_bot(pid) and math.min(M.RULES.max_multiplier,base+M.bonus(e,pid)) or base
end
function M.scale(e,pid,kind,amount)
 if amount<=0 then return amount end
 local multiplier=M.multiplier(e,pid)
 -- Carry fractional rewards so frequent 1-gold ticks still receive the bonus.
 e.bot_reward_remainders=e.bot_reward_remainders or {}
 local key=pid or -1
 local rem=e.bot_reward_remainders[key] or {};e.bot_reward_remainders[key]=rem
 local exact=amount*multiplier+(rem[kind] or 0)
 local whole=math.floor(exact+0.000000001)
 rem[kind]=math.max(0,exact-whole)
 return whole
end
function M.hero_kill(e,victim,attacker)
 if e.room.phase~='pregame' and e.room.phase~='playing' then return end
 if not victim or not victim.IsRealHero or not victim:IsRealHero() or victim:IsIllusion()
  or (victim.IsClone and victim:IsClone()) or (victim.IsTempestDouble and victim:IsTempestDouble())
  or (victim.IsReincarnating and victim:IsReincarnating()) then return end
 if not attacker or not attacker.GetPlayerOwnerID then return end
 local pid=attacker:GetPlayerOwnerID()
 if not PlayerResource:IsValidPlayerID(pid) or not PlayerResource:IsFakeClient(pid) then return end
 local killer=PlayerResource:GetSelectedHeroEntity(pid)
 if not killer or killer:GetTeamNumber()==victim:GetTeamNumber() then return end
 -- Player-owned summons/illusions attribute the kill to their owning bot.
 e.bot_death_bonus=e.bot_death_bonus or {};e.bot_death_bonus[pid]=math.max(0,(e.bot_death_bonus[pid] or 0)-M.RULES.kill_reduce_layers)
 if e.bot_reward_remainders then e.bot_reward_remainders[pid]=nil end
 M.report(e,pid,killer:GetTeamNumber(),'BOT_COMEBACK_REDUCED')
end
function M.killed(e,h)
 if e.room.phase~='pregame' and e.room.phase~='playing' then return end
 if not h or not h.IsRealHero or not h:IsRealHero() or h:IsIllusion()
  or (h.IsClone and h:IsClone()) or (h.IsTempestDouble and h:IsTempestDouble())
  or (h.IsReincarnating and h:IsReincarnating()) then return end
 local pid=h:GetPlayerOwnerID()
 if not PlayerResource:IsValidPlayerID(pid) or not PlayerResource:IsFakeClient(pid)
  or PlayerResource:GetSelectedHeroEntity(pid)~=h then return end
 e.bot_death_bonus=e.bot_death_bonus or {}
 e.bot_death_bonus[pid]=math.min(M.RULES.max_layers,(e.bot_death_bonus[pid] or 0)+1)
 M.report(e,pid,h:GetTeamNumber(),'BOT_COMEBACK')
end
function M.report(e,pid,team,event)
 local base=M.base()
 e:emit(event,{pid=pid,layers=e.bot_death_bonus[pid],
  base_multiplier=base,gold_multiplier=M.multiplier(e,pid),xp_multiplier=M.multiplier(e,pid)})
end
return M
