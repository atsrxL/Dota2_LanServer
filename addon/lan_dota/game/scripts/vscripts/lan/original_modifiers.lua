-- Adapted from installed AI Fun 956357541 global_modifiers.lua; conventional options only.
modifier_tower_endure = class({})

function modifier_tower_endure:IsPurgable() return false end
function modifier_tower_endure:IsDebuff() return false end
function modifier_tower_endure:GetTexture() return "tower_endure" end
function modifier_tower_endure:OnCreated()
	if IsClient() then return end
	local hParent = self:GetParent()
	local iHealth = hParent.iHP or hParent:GetMaxHealth()
	self:GetParent():SetContextThink('lan_endure',function ()
		if hParent == nil or hParent:IsNull() then return end
		hParent:SetMaxHealth(self:GetStackCount()*iHealth)
		hParent:SetBaseMaxHealth(self:GetStackCount()*iHealth)
		hParent:SetHealth(self:GetStackCount()*iHealth)
	end,0.1)
end

function modifier_tower_endure:DeclareFunctions()
	return {
		MODIFIER_PROPERTY_PHYSICAL_ARMOR_BONUS,
		MODIFIER_PROPERTY_HEALTH_REGEN_CONSTANT,
		MODIFIER_PROPERTY_TOOLTIP
	}
end

function modifier_tower_endure:GetModifierConstantHealthRegen()
	return 10*(self:GetStackCount()-1)
end

function modifier_tower_endure:GetModifierPhysicalArmorBonus()	
	local sName = self:GetParent():GetName()
	
	if string.match(sName, "healer") then		
		return 17*(self:GetStackCount()-1)/2
	elseif string.match(sName, "fort") then		
		return 13*(self:GetStackCount()-1)/2
	elseif string.match(sName, "range") then		
		return 9*(self:GetStackCount()-1)/2
	elseif string.match(sName, "melee") then		
		return 15*(self:GetStackCount()-1)/2
	elseif string.match(sName, "1") then 
		return 12*(self:GetStackCount()-1)/2
	elseif string.match(sName, "2") then		
		return 16*(self:GetStackCount()-1)/2
	elseif string.match(sName, "3") then		
		return 16*(self:GetStackCount()-1)/2
	elseif string.match(sName, "4") then		
		return 21*(self:GetStackCount()-1)/2
	end
end

function modifier_tower_endure:OnTooltip()
	return (self:GetStackCount()-1)*100
end

modifier_tower_power = class({})


function modifier_tower_power:DeclareFunctions()
	return {
		MODIFIER_PROPERTY_BASEDAMAGEOUTGOING_PERCENTAGE,
		MODIFIER_PROPERTY_ATTACKSPEED_BONUS_CONSTANT,
		MODIFIER_EVENT_ON_ATTACK_LANDED,
		MODIFIER_PROPERTY_TOOLTIP		
	}
end

function modifier_tower_power:IsPurgable() return false end
function modifier_tower_power:IsDebuff() return false end
function modifier_tower_power:GetTexture() return "tower_power" end
function modifier_tower_power:OnAttackLanded(keys)
	if keys.attacker ~= self:GetParent() then return end
	local tTargets = FindUnitsInRadius(keys.attacker:GetTeamNumber(), keys.target:GetOrigin(), nil, (self:GetStackCount()-1)*75, DOTA_UNIT_TARGET_TEAM_ENEMY, DOTA_UNIT_TARGET_BASIC+DOTA_UNIT_TARGET_HERO, DOTA_UNIT_TARGET_FLAG_MAGIC_IMMUNE_ENEMIES, FIND_ANY_ORDER, false)
	
	for i, v in ipairs(tTargets) do
		if v ~= keys.target then
			ApplyDamage({
				attacker = keys.attacker,
				victim = v,
				damage = keys.damage,
				damage_type = DAMAGE_TYPE_PHYSICAL,
				damage_flags = DOTA_DAMAGE_FLAG_IGNORES_PHYSICAL_ARMOR
			})
		end
	end
end

function modifier_tower_power:OnTooltip()
	return 75*(self:GetStackCount()-1)
end

function modifier_tower_power:GetModifierAttackSpeedBonus_Constant() return 500/9*(self:GetStackCount()-1) end


function modifier_tower_power:GetModifierBaseDamageOutgoing_Percentage()
	return 100*(self:GetStackCount()-1)
end


modifier_fast_courier = class({IsPurgable=function() return false end})
function modifier_fast_courier:DeclareFunctions()
	return {
			MODIFIER_PROPERTY_MOVESPEED_MAX,
			MODIFIER_PROPERTY_MOVESPEED_LIMIT,
			MODIFIER_PROPERTY_MOVESPEED_ABSOLUTE,}
end


function modifier_fast_courier:GetModifierMoveSpeed_Max()
	return 2000
end

function modifier_fast_courier:GetModifierMoveSpeed_Limit()
	return 2000
end

function modifier_fast_courier:GetModifierMoveSpeed_Absolute()
	return 2000
end

function modifier_fast_courier:GetTexture() return 'void_demon_mass_haste' end

modifier_anti_diving=class({})
function modifier_anti_diving:IsPurgable() return false end
function modifier_anti_diving:RemoveOnDeath() return false end
function modifier_anti_diving:IsHidden() 
	if self:GetStackCount() <= 0 then return true else return false end
end
function modifier_anti_diving:DeclareFunctions()
	return {MODIFIER_PROPERTY_TOTALDAMAGEOUTGOING_PERCENTAGE, MODIFIER_EVENT_ON_TAKEDAMAGE}
end
function modifier_anti_diving:GetModifierTotalDamageOutgoing_Percentage()
	return -10*self:GetStackCount()
end

function modifier_anti_diving:OnCreated()
	self:StartIntervalThink(0.1)
	self.fTime = 0
end
function modifier_anti_diving:GetTexture()
	return "anti_diving"
end
function modifier_anti_diving:OnIntervalThink()
	if IsClient() or not Entities:FindByName(nil, "ent_dota_fountain_bad") then return end
	local fDistance
	if self:GetParent():GetTeam() == DOTA_TEAM_BADGUYS then
		fDistance = CalcDistanceBetweenEntityOBB(self:GetParent(), Entities:FindByName(nil, "ent_dota_fountain_good"))
	else
		fDistance = CalcDistanceBetweenEntityOBB(self:GetParent(), Entities:FindByName(nil, "ent_dota_fountain_bad"))
	
	end
	if fDistance < 1200 then
		self.fTime = self.fTime + 0.1
	else
		self.fTime = self.fTime - 0.05
	end
	if self.fTime < 0 then self.fTime = 0 end
	if self.fTime  > 15 then self.fTime  = 15 end
	local iStackCount = math.floor(self.fTime)-5
	if iStackCount < 0 then
		iStackCount = 0
	end
	self:SetStackCount(iStackCount)
end

modifier_bot_protection = class({})
function modifier_bot_protection:IsPurgable() return false end
function modifier_bot_protection:RemoveOnDeath() return false end
function modifier_bot_protection:DeclareFunctions()
	return {MODIFIER_PROPERTY_TOTALDAMAGEOUTGOING_PERCENTAGE, MODIFIER_PROPERTY_INCOMING_DAMAGE_PERCENTAGE, MODIFIER_EVENT_ON_DEATH}
end
function modifier_bot_protection:GetTexture() return "Bot_hard_icon" end
function modifier_bot_protection:OnDeath(keys)
	if keys.unit:IsRealHero() then
		local iPlayerID = self:GetParent():GetPlayerOwnerID()
		self:SetStackCount(PlayerResource:GetDeaths(iPlayerID)-PlayerResource:GetKills(iPlayerID)-5)
	end
end

function modifier_bot_protection:IsHidden()
	if self:GetStackCount() <= 0 then return true else return false end
end

function modifier_bot_protection:GetModifierIncomingDamage_Percentage()
	local iPercentage = -self:GetStackCount()*5
	if iPercentage < -50 then iPercentage = -50 end
	return iPercentage
end

function modifier_bot_protection:GetModifierTotalDamageOutgoing_Percentage()
	local iPercentage = self:GetStackCount()*10
	if iPercentage > 100 then iPercentage = 100 end
	return iPercentage
end


modifier_tower_invulnerable_watcher = class({IsPurgable=function() return false end})

function modifier_tower_invulnerable_watcher:OnCreated()
	self.tWatchList = {}
end

function modifier_tower_invulnerable_watcher:DeclareFunctions()
	return {MODIFIER_EVENT_ON_DEATH}
end

function modifier_tower_invulnerable_watcher:AddNewWatchee(hT)
	-- print("new watchee added", hT:GetUnitName())
	table.insert(self.tWatchList, hT)
	if hT and hT:IsAlive() then
		hT:AddNewModifier(hT, nil, "modifier_invulnerable", {})
	end
end


function modifier_tower_invulnerable_watcher:OnDeath(keys)
	if keys.unit:GetClassname() ~= "npc_dota_tower" then
		return
	end
	local hParent = self:GetParent()

	if keys.unit == self:GetParent() then
		for _, hT in pairs(self.tWatchList) do
			if hT and (not hT:IsNull()) and hT:IsAlive() then
				hT:RemoveModifierByName("modifier_invulnerable")
			end
		end
		
		if self:GetParent():GetName() == "npc_dota_tower" then
			-- self:GetParent():AddEffects(EF_NODRAW)
			local sParName
			if hParent:GetTeamNumber() == DOTA_TEAM_BADGUYS then
				sParName = "particles/dire_fx/dire_tower002_destruction.vpcf"
			else
				sParName = "particles/radiant_fx/radiant_tower002_destruction.vpcf"
			end
			local par = ParticleManager:CreateParticle(sParName, PATTACH_ABSORIGIN, self:GetParent()) 
			ParticleManager:SetParticleControl(par, 4, self:GetParent().vColor)
			hParent:SetModelScale(0.001)
		end

		return 
	end
	
	if self:GetParent():IsAlive() then -- some other tower destroyed, check invulnerability later
		self:StartIntervalThink(0.1)
	end
	
end

function modifier_tower_invulnerable_watcher:OnIntervalThink()
	-- print("check invulnerability")
	for _, hT in pairs(self.tWatchList) do
		if hT and (not hT:IsNull()) and hT:IsAlive() then
			hT:AddNewModifier(hT, nil, "modifier_invulnerable", {})
		end
	end
	self:StartIntervalThink(-1)
end

function modifier_tower_invulnerable_watcher:OnDestroy()
	self.tWatchList = nil
end

