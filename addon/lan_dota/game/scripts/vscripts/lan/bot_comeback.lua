-- Per-bot triangular income stacks, capped at nine (5x from a 1x baseline).
local M={}
function M.bonus(e,pid,kind)
 if type(pid)~='number' or not PlayerResource:IsValidPlayerID(pid)
  or not PlayerResource.IsFakeClient or not PlayerResource:IsFakeClient(pid) then return 0 end
 local deaths=e.bot_death_bonus and e.bot_death_bonus[pid] or 0
 return deaths*(deaths+1)/20
end
function M.scale(e,pid,kind,amount,base)
 if amount<=0 then return amount end
 local bonus=M.bonus(e,pid,kind)
 local bot=type(pid)=='number' and PlayerResource:IsValidPlayerID(pid) and PlayerResource.IsFakeClient and PlayerResource:IsFakeClient(pid)
 local multiplier=bot and math.min(5,base+bonus) or base
 if not bot then return math.floor(amount*multiplier) end
 -- Carry fractional rewards so frequent 1-gold ticks still receive the bonus.
 e.bot_reward_remainders=e.bot_reward_remainders or {}
 local rem=e.bot_reward_remainders[pid] or {};e.bot_reward_remainders[pid]=rem
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
 e.bot_death_bonus=e.bot_death_bonus or {};e.bot_death_bonus[pid]=math.max(0,(e.bot_death_bonus[pid] or 0)-3)
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
 e.bot_death_bonus[pid]=math.min(9,(e.bot_death_bonus[pid] or 0)+1)
 M.report(e,pid,h:GetTeamNumber(),'BOT_COMEBACK')
end
function M.report(e,pid,team,event)
 local side=team==3 and 'dire' or 'radiant'
 e:emit(event,{pid=pid,layers=e.bot_death_bonus[pid],
  gold_multiplier=math.min(5,e.room.options[side..'_gold_multiplier']*(e.room.options.gold_percent or 100)/100+M.bonus(e,pid,'gold')),
  xp_multiplier=math.min(5,e.room.options[side..'_xp_multiplier']+M.bonus(e,pid,'xp'))})
end
return M
