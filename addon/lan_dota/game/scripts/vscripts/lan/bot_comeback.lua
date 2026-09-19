-- Per-bot, per-match additive income bonuses; no change to native bot AI.
local M={}
function M.bonus(e,pid,kind)
 if type(pid)~='number' or not PlayerResource:IsValidPlayerID(pid)
  or not PlayerResource.IsFakeClient or not PlayerResource:IsFakeClient(pid) then return 0 end
 local deaths=e.bot_death_bonus and e.bot_death_bonus[pid] or 0
 return deaths*(kind=='gold' and 0.2 or 0.1)
end
function M.scale(e,pid,kind,amount,base)
 if amount<=0 then return amount end
 if e.bot_income_reset and e.bot_income_reset[pid] then base=1 end
 local bonus=M.bonus(e,pid,kind)
 if bonus==0 then return math.floor(amount*base) end
 -- Carry fractional rewards so frequent 1-gold ticks still receive the bonus.
 e.bot_reward_remainders=e.bot_reward_remainders or {}
 local rem=e.bot_reward_remainders[pid] or {};e.bot_reward_remainders[pid]=rem
 local exact=amount*(base+bonus)+(rem[kind] or 0)
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
 e.bot_death_bonus=e.bot_death_bonus or {};e.bot_death_bonus[pid]=0
 e.bot_income_reset=e.bot_income_reset or {};e.bot_income_reset[pid]=true
 if e.bot_reward_remainders then e.bot_reward_remainders[pid]=nil end
 e:emit('BOT_COMEBACK_RESET',{pid=pid,gold_multiplier=1,xp_multiplier=1})
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
 e.bot_death_bonus[pid]=(e.bot_death_bonus[pid] or 0)+1
 local side=h:GetTeamNumber()==3 and 'dire' or 'radiant'
 e:emit('BOT_COMEBACK',{pid=pid,deaths=e.bot_death_bonus[pid],
  gold_multiplier=(e.bot_income_reset and e.bot_income_reset[pid] and 1 or e.room.options[side..'_gold_multiplier']*(e.room.options.gold_percent or 100)/100)+M.bonus(e,pid,'gold'),
  xp_multiplier=(e.bot_income_reset and e.bot_income_reset[pid] and 1 or e.room.options[side..'_xp_multiplier'])+M.bonus(e,pid,'xp')})
end
return M
