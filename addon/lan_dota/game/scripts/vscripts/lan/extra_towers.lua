-- Adapted from AI Fun events.lua extra-tower placement and dependency chain.
local M={}
local function CreateTowerBetween (self,hT1, hT2, count, bHighland) -- 
	if count == 0 then return end
	local vOri1 = hT1:GetAbsOrigin()
	local vOri2 = hT2:GetAbsOrigin()
	local fArmor1 = hT1:GetPhysicalArmorBaseValue()
	local fArmor2 = hT2:GetPhysicalArmorBaseValue()
	local iHP1 = hT1:GetMaxHealth()
	local iHP2 = hT2:GetMaxHealth()
	local iDamageMin1 = hT1:GetBaseDamageMin()
	local iDamageMin2 = hT2:GetBaseDamageMin()
	local iDamageMax1 = hT1:GetBaseDamageMax()
	local iDamageMax2 = hT2:GetBaseDamageMax()
	local iPreviousEntIndex = -1
	for i = 1, count do
		local vPos = GetGroundPosition(vOri2 + (vOri1 - vOri2) * (i / (count+1)),nil)
		local hTower = CreateUnitByName(hT1:GetUnitName(), vPos, false, nil, nil, hT1:GetTeamNumber())
		local fArmor = fArmor2 + (fArmor1 - fArmor2) * (i / (count+1))
		hTower.iHP = math.floor(iHP2 + (iHP1 - iHP2) * (i / (count+1)))
		local iDamageMin = math.floor(iDamageMin2 + (iDamageMin1 - iDamageMin2) * (i / (count+1)))
		local iDamageMax = math.floor(iDamageMax2 + (iDamageMax1 - iDamageMax2) * (i / (count+1)))
		hTower:SetPhysicalArmorBaseValue(fArmor)
		hTower:SetBaseDamageMin(iDamageMin)
		hTower:SetBaseDamageMax(iDamageMax)
		hTower:SetModel(hT1:GetModelName())
		hTower:SetForwardVector(hT2:GetForwardVector())
		hTower.vColor = hT1:GetRenderColor()

		if self.iExtraTowerPhased > 0 then hTower:AddNewModifier(hTower, nil, "modifier_phased",nil) end
		
		hTower:SetRenderColor(hTower.vColor.x, hTower.vColor.y, hTower.vColor.z)

		if i == 1 then
			hTower:AddNewModifier(hTower, nil, "modifier_tower_invulnerable_watcher", {}):AddNewWatchee(hT2)
		end
		if i == count then
			hT1:AddNewModifier(hT1, nil, "modifier_tower_invulnerable_watcher", {}):AddNewWatchee(hTower)
		end
		if i ~= 1 then
			hTower:AddNewModifier(hTower, nil, "modifier_tower_invulnerable_watcher", {}):AddNewWatchee(EntIndexToHScript(iPreviousEntIndex))
		end
		iPreviousEntIndex = hTower:entindex()
		if bHighland then
			table.insert(self.tExtraTower_HighLand, hTower)
		else
			table.insert(self.tExtraTower, hTower)
		end
	end
end

local function TN(team, tire, lane)
	return "npc_dota_"..team.."_tower"..tostring(tire).."_"..lane
end

function M.create(self)
	if self.iExtraTower == 0 then return end

	self.tExtraTower = {}
	self.tExtraTower_HighLand = {}
	local tTowersList = Entities:FindAllByClassname('npc_dota_tower')
	local tTowers = {}
	
	for _, v in pairs(tTowersList) do
		-- print(v:GetUnitName())
		tTowers[v:GetUnitName()] = v
	end

	local tLane = {"top", "mid", "bot"}
	local tTeam = {"goodguys", "badguys"}
	for _, lane in ipairs(tLane) do
		for _, team in ipairs(tTeam) do
			CreateTowerBetween(self, tTowers[TN(team, 1, lane)],tTowers[TN(team, 2, lane)], self.iExtraTower, false)
			CreateTowerBetween(self, tTowers[TN(team, 2, lane)],tTowers[TN(team, 3, lane)], self.iExtraTower,false)
		end
	end
end



return M
