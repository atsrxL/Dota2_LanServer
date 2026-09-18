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


