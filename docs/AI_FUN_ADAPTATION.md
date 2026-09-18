# Installed AI Fun UI adaptation

Source: user's Windows Workshop item 956357541, DOTA2 AI Fun 12v12, publish_data timestamp 1773370668. Read-only extraction from 956357541.vpk, preserved outside repository at deployment-1.3.0/fun-reference.zip. Original subscription untouched.

Adapted actual game_mode.js AddDropDown implementation (dynamic option registration with AddOption, selection via oninputsubmit) and option-row CSS from custom_loading_screen.css. Removed localization dependency for these few labels, Tools overrides, multiplayer broadcasts/voting, Fun options, external links and map artwork. This is a scoped UI adaptation, not a full fork of its gamemode or AI implementation. Local personal deployment; upstream licensing was not present in the extracted subset, no public push performed.

Single-player confirm uses existing authenticated lan_action source resolution with new solo_start action, validated option allowlist, host/revision/one-human checks, automatic Radiant assignment, readiness and guarded start. Uses existing selected Tiandixing 1573671599 and one-shot BotPopulate route. No client-supplied PlayerID authorization.

42 addon tests pass including solo duplicate/start/count validation and adapted dynamic-control mock. Real Workshop Tools compilation passed, r8 deployed to .98 and CT270. Actual r8 visual/AI behavior still requires client verification. No claim that neutral tier unlock configuration is implemented.

## r9 conventional settings and cheat-state correction

Restored per-team gold/XP multipliers, starting gold/level, team size (1–12), respawn percentage, buyback cooldown, tower power, building endurance, extra towers and phased state, max level, universal shop, fast courier, bot protection and anti-diving. UI uses the adapted original dynamic option generator. Tower/anti-diving/bot-protection/courier modifiers and extra-tower dependency chain are adapted from installed original Lua; no Fun hero/items/lottery/skill-book code. Extended XP curve preserves the original reference's 7.23 base curve and extends it without its max-level-minus-five mismatch; custom max levels are therefore a custom curve, not current Valve XP balance. Neutral item unlock timing is still pending.

Uses original Tutorial:AddBot strategy-time fill with configured counts and one-shot verification, while retaining BotPopulate fallback for engines without Tutorial API. Actual new BOOT reports sv_cheats=true and GameRules:IsCheatMode=false: these are distinct on this dedicated build. User authorized default cheats; addon initializes sv_cheats=true and checks actual Convars value. Do not treat GameRules false as proof sv_cheats is off.

Real r9 compilation passed; 42 addon tests include asymmetric 3v4 Tutorial fill, decimal multiplier, no duplicate population. Live cheat convar verified true. Individual rule effects and actual Tutorial AI behavior require gameplay verification.
