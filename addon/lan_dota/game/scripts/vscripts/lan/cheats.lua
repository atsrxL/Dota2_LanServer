-- Personal LAN chat cheats. This does not change the GC lobby cheat flag.
local M={}
M.bat_min,M.bat_max=0.1,10
M.abilities={death_prophet_witchcraft=true,razor_unstable_current=true,bloodseeker_thirst=true,winter_wyvern_eldwurms_edda=true,tinker_eureka=true,silencer_brain_drain=true}
function M.hero_tool(e,pid,action,input)
 local h=PlayerResource:GetSelectedHeroEntity(pid)
 if not h then return false,'尚未选择英雄' end
 local name=action:match('^self_ability_(.+)$')
 if action=='self_add_ability' then
  if type(input)~='string' or #input>128 then return false,'请输入有效的技能内部名称' end
  name=input:match('^%s*(.-)%s*$')
  if #name==0 or #name>96 or not name:match('^[a-z][a-z0-9_]*$') then return false,'只填技能内部名称，例如 bloodseeker_thirst' end
  if type(GetAbilityKeyValuesByName)=='function' then
   local kv=GetAbilityKeyValuesByName(name)
   if type(kv)~='table' or next(kv)==nil then return false,'技能名称不存在：'..name end
  end
 end
 if name then
  if action~='self_add_ability' and not M.abilities[name] then return false,'不允许添加该技能' end
  if h:FindAbilityByName(name) then return false,'已拥有该技能' end
  local a=h:AddAbility(name)
  if not a then return false,'当前游戏版本无法添加该技能：'..name end
  local kv=a.GetAbilityKeyValues and a:GetAbilityKeyValues() or {}
  local innate=kv and (kv.Innate==true or tonumber(kv.Innate)==1)
  local trained=action=='self_add_ability' and not innate
  if trained then a:SetLevel(0)
  else a:SetLevel(math.max(1,a:GetMaxLevel())) end
  -- Remember panel-added abilities; only these may be removed again.
  -- Trained ones refund the skill points the player spent on them.
  h.lan_added_abilities=h.lan_added_abilities or {}
  h.lan_added_abilities[name]={refund=trained}
  e:emit('MENU_ABILITY',{pid=pid,ability=name,level=a:GetLevel()})
  return true,'已添加：'..name
 end
 if action=='self_remove_ability' then
  return M.remove_ability(e,pid,h,input)
 end
 if action=='self_bat_down' or action=='self_bat_up' or action=='self_bat_reset' then
  if not h.lan_initial_bat then h.lan_initial_bat=h:GetBaseAttackTime(false) end
  local value=h.lan_initial_bat
  if action~='self_bat_reset' then
   local current=h:GetBaseAttackTime(false)
   local up=action=='self_bat_up'
   local low=math.max(M.bat_min,h.lan_initial_bat-0.3)
   local high=h.lan_initial_bat+0.3
   -- Clamp so a value set by -basetime outside the range steps back to the nearest edge.
   value=math.floor((current+(up and 0.1 or -0.1))*100+0.5)/100
   value=math.max(low,math.min(high,value))
   if (up and value<=current+0.000001) or (not up and value>=current-0.000001) then
    return false,string.format('面板范围 %.2f～%.2f 秒；可用 -basetime 数值直接设置',low,high)
   end
  end
  h:SetBaseAttackTime(value)
  e:emit('MENU_BAT',{pid=pid,value=h:GetBaseAttackTime(false),initial=h.lan_initial_bat})
  return true,string.format('基础攻击间隔 %.2f 秒（初始 %.2f）',h:GetBaseAttackTime(false),h.lan_initial_bat)
 end
 return false,'未知操作'
end
function M.handle(e,k)
 if type(k)~='table' or type(k.text)~='string' then return end
 local cmd,arg=k.text:match('^%s*(%-%a+)%s*(.-)%s*$')
 if cmd~='-gold' and cmd~='-lvlup' and cmd~='-refresh' and cmd~='-respawn' and cmd~='-basetime' then return end
 local pid=tonumber(k.playerid)
 -- player_chat is emitted by the engine, not a custom client payload.
 if not pid or not PlayerResource:IsValidPlayerID(pid) or not PlayerResource:GetPlayer(pid) then return end
 if PlayerResource.IsFakeClient and PlayerResource:IsFakeClient(pid) then return end
 if not Convars:GetBool('sv_cheats') then return end
 local h=PlayerResource:GetSelectedHeroEntity(pid)
 if not h then return end
 local result={pid=pid,command=cmd}
 if cmd=='-basetime' then
  local n=arg:match('^%d*%.?%d+$') and tonumber(arg)
  if not n or n<M.bat_min or n>M.bat_max then
   e:reply(pid,false,string.format('用法：-basetime %g～%g 之间的秒数，例如 -basetime 1.7',M.bat_min,M.bat_max));return
  end
  if not h.lan_initial_bat then h.lan_initial_bat=h:GetBaseAttackTime(false) end
  h:SetBaseAttackTime(n)
  result.after=h:GetBaseAttackTime(false)
  e:reply(pid,true,string.format('基础攻击间隔已设置为 %g 秒',n))
 elseif cmd=='-gold' then
  local n=tonumber(arg)
  if not n or n~=math.floor(n) or math.abs(n)>999999 then e:reply(pid,false,'用法：-gold 整数（范围 -999999～999999）');return end
  local before=PlayerResource:GetGold(pid)
  -- SetGold avoids multiplying the cheat amount through the income filter.
  local unreliable=PlayerResource:GetUnreliableGold(pid)
  local reliable=PlayerResource:GetReliableGold(pid)
  local target=math.max(0,before+n)
  h:SetGold(math.min(reliable,target),true)
  h:SetGold(math.max(0,target-math.min(reliable,target)),false)
  result.before=before;result.after=PlayerResource:GetGold(pid)
 elseif cmd=='-lvlup' then
  local n=tonumber(arg)
  if not n or n~=math.floor(n) or n<1 or n>1600 then e:reply(pid,false,'用法：-lvlup 正整数');return end
  result.before=h:GetLevel()
  local target=math.min(e.room.options.max_level or 30,h:GetLevel()+n)
  for i=h:GetLevel()+1,target do h:HeroLevelUp(false) end
  result.after=h:GetLevel()
 else
  if arg~='' then return end
  if cmd=='-respawn' and not h:IsAlive() then h:RespawnHero(false,false) end
  h:SetHealth(h:GetMaxHealth());h:SetMana(h:GetMaxMana())
  for i=0,23 do local a=h:GetAbilityByIndex(i);if a then a:EndCooldown() end end
  for i=0,16 do local item=h:GetItemInSlot(i);if item then item:EndCooldown() end end
  result.alive=h:IsAlive()
 end
 e:emit('CHAT_CHEAT',result)
end
function M.remove_ability(e,pid,h,input)
 local name=type(input)=='string' and input:match('^%s*(.-)%s*$') or ''
 if #name==0 or #name>96 or not name:match('^[a-z][a-z0-9_]*$') then
  return false,'只填技能内部名称，例如 bloodseeker_thirst'
 end
 local added=h.lan_added_abilities and h.lan_added_abilities[name]
 if not added then return false,'只能删除通过面板添加的技能：'..name end
 local a=h:FindAbilityByName(name)
 if not a then
  h.lan_added_abilities[name]=nil
  return false,'英雄身上没有该技能：'..name
 end
 local refund=added.refund and a:GetLevel() or 0
 -- RemoveAbility leaves passive/intrinsic modifiers behind; drop them first.
 if h.FindAllModifiers then
  for _,m in ipairs(h:FindAllModifiers()) do
   if m.GetAbility and m:GetAbility()==a then m:Destroy() end
  end
 end
 h:RemoveAbilityByHandle(a)
 h.lan_added_abilities[name]=nil
 if refund>0 then h:SetAbilityPoints(h:GetAbilityPoints()+refund) end
 e:emit('MENU_ABILITY_REMOVED',{pid=pid,ability=name,refund=refund})
 if refund>0 then return true,string.format('已删除：%s，返还 %d 技能点',name,refund) end
 return true,'已删除：'..name
end
function M.button(e,pid,action,input)
 if type(action)~='string' then return false,'未知操作' end
 local actions={self_respawn=true,self_refresh=true,self_gold=true,ally_gold=true,enemy_gold=true,ally_level=true,enemy_level=true}
 local ability=type(action)=='string' and action:match('^self_ability_(.+)$')
 local hero_tool=action=='self_add_ability' or action=='self_remove_ability' or (ability and M.abilities[ability])
  or action=='self_bat_down' or action=='self_bat_up' or action=='self_bat_reset'
 if not actions[action] and not hero_tool then return false,'未知操作' end
 if e.room.phase~='pregame' and e.room.phase~='playing' then return false,'进入比赛后才能操作' end
 local p=e.room.players[pid]
 if not p or not p.connected or not p.hello then return false,'ui_handshake_required' end
 if not Convars:GetBool('sv_cheats') then return false,'作弊开关未开启' end
 if hero_tool then
  local ok,success,message=pcall(M.hero_tool,e,pid,action,input)
  if not ok then e:emit('MENU_TOOL_ERROR',{pid=pid,action=action,error=tostring(success)});return false,'操作失败，已记录日志' end
  return success,message
 end
 local team=PlayerResource:GetTeam(pid)
 local count=0
 for target=0,63 do
  if PlayerResource:IsValidPlayerID(target) then
   local own=action:sub(1,5)=='self_'
   local bot=PlayerResource.IsFakeClient and PlayerResource:IsFakeClient(target)
   local same=PlayerResource:GetTeam(target)==team
   local selected=(own and target==pid) or (not own and bot and ((action:sub(1,5)=='ally_' and same) or (action:sub(1,6)=='enemy_' and not same and (PlayerResource:GetTeam(target)==2 or PlayerResource:GetTeam(target)==3))))
   local h=selected and PlayerResource:GetSelectedHeroEntity(target) or nil
   if h then
    if action:find('_gold',1,true) then
     h:SetGold(PlayerResource:GetUnreliableGold(target)+1000,false)
    elseif action:find('_level',1,true) then
     if h:GetLevel()<(e.room.options.max_level or 30) then h:HeroLevelUp(false) end
    else
     if action=='self_respawn' and not h:IsAlive() then h:RespawnHero(false,false) end
     if action=='self_respawn' and type(GetTeamFountain)=='function' and type(FindClearSpaceForUnit)=='function' then
      local fountain=GetTeamFountain(team);if fountain then FindClearSpaceForUnit(h,fountain:GetAbsOrigin(),true) end
     end
     h:SetHealth(h:GetMaxHealth());h:SetMana(h:GetMaxMana())
     for n=0,23 do local a=h:GetAbilityByIndex(n);if a then a:EndCooldown() end end
     for n=0,16 do local item=h:GetItemInSlot(n);if item then item:EndCooldown() end end
    end
    count=count+1
   end
  end
 end
 e:emit('MENU_CHEAT',{pid=pid,action=action,targets=count})
 return count>0,count>0 and ('已执行，目标 '..count..' 个') or '没有可操作的英雄'
end
function M.init(e)
 if type(ListenToGameEvent)~='function' then return end
 ListenToGameEvent('player_chat',function(k)
  local ok,err=pcall(M.handle,e,k)
  if not ok then e:emit('CHAT_CHEAT_ERROR',tostring(err));e:reply(tonumber(k.playerid),false,'作弊指令执行失败，已记录日志。') end
 end,nil)
 e:emit('CHAT_CHEATS','enabled: -gold -lvlup -refresh -respawn -basetime; addon_chat_bridge')
end
return M
