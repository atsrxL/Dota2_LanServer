-- Personal LAN chat cheats. This does not change the GC lobby cheat flag.
local M={}
function M.handle(e,k)
 if type(k)~='table' or type(k.text)~='string' then return end
 local cmd,arg=k.text:match('^%s*(%-%a+)%s*(.-)%s*$')
 if cmd~='-gold' and cmd~='-lvlup' and cmd~='-refresh' and cmd~='-respawn' then return end
 local pid=tonumber(k.playerid)
 -- player_chat is emitted by the engine, not a custom client payload.
 if not pid or not PlayerResource:IsValidPlayerID(pid) or not PlayerResource:GetPlayer(pid) then return end
 if PlayerResource.IsFakeClient and PlayerResource:IsFakeClient(pid) then return end
 if not Convars:GetBool('sv_cheats') then return end
 local h=PlayerResource:GetSelectedHeroEntity(pid)
 if not h then return end
 local result={pid=pid,command=cmd}
 if cmd=='-gold' then
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
function M.init(e)
 if type(ListenToGameEvent)~='function' then return end
 ListenToGameEvent('player_chat',function(k)
  local ok,err=pcall(M.handle,e,k)
  if not ok then e:emit('CHAT_CHEAT_ERROR',tostring(err));e:reply(tonumber(k.playerid),false,'作弊指令执行失败，已记录日志。') end
 end,nil)
 e:emit('CHAT_CHEATS','enabled: -gold -lvlup -refresh -respawn; addon_chat_bridge')
end
return M
