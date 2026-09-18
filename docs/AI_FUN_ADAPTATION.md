# Installed AI Fun UI adaptation

Source: user's Windows Workshop item 956357541, DOTA2 AI Fun 12v12, publish_data timestamp 1773370668. Read-only extraction from 956357541.vpk, preserved outside repository at deployment-1.3.0/fun-reference.zip. Original subscription untouched.

Adapted actual game_mode.js AddDropDown implementation (dynamic option registration with AddOption, selection via oninputsubmit) and option-row CSS from custom_loading_screen.css. Removed localization dependency for these few labels, Tools overrides, multiplayer broadcasts/voting, Fun options, external links and map artwork. This is a scoped UI adaptation, not a full fork of its gamemode or AI implementation. Local personal deployment; upstream licensing was not present in the extracted subset, no public push performed.

Single-player confirm uses existing authenticated lan_action source resolution with new solo_start action, validated option allowlist, host/revision/one-human checks, automatic Radiant assignment, readiness and guarded start. Uses existing selected Tiandixing 1573671599 and one-shot BotPopulate route. No client-supplied PlayerID authorization.

42 addon tests pass including solo duplicate/start/count validation and adapted dynamic-control mock. Real Workshop Tools compilation passed, r8 deployed to .98 and CT270. Actual r8 visual/AI behavior still requires client verification. No claim that neutral tier unlock configuration is implemented.

## r9 conventional settings and cheat-state correction

Restored per-team gold/XP multipliers, starting gold/level, team size (1–12), respawn percentage, buyback cooldown, tower power, building endurance, extra towers and phased state, max level, universal shop, fast courier, bot protection and anti-diving. UI uses the adapted original dynamic option generator. Tower/anti-diving/bot-protection/courier modifiers and extra-tower dependency chain are adapted from installed original Lua; no Fun hero/items/lottery/skill-book code. Extended XP curve preserves the original reference's 7.23 base curve and extends it without its max-level-minus-five mismatch; custom max levels are therefore a custom curve, not current Valve XP balance. Neutral item unlock timing is still pending.

Uses original Tutorial:AddBot strategy-time fill with configured counts and one-shot verification, while retaining BotPopulate fallback for engines without Tutorial API. Actual new BOOT reports sv_cheats=true and GameRules:IsCheatMode=false: these are distinct on this dedicated build. User authorized default cheats; addon initializes sv_cheats=true and checks actual Convars value. Do not treat GameRules false as proof sv_cheats is off.

Real r9 compilation passed; 42 addon tests include asymmetric 3v4 Tutorial fill, decimal multiplier, no duplicate population. Live cheat convar verified true. Individual rule effects and actual Tutorial AI behavior require gameplay verification.

## r10 user-accepted AI entry and reduced options

User confirmed r9 entered gameplay and AI appeared (not full behavior validation). Removed universal shop, fast courier, extra towers/phased setting and anti-diving from UI, server allowlists, defaults and effects. Retained building endurance/power and bot protection. Native difficulty now 0 passive / 1 easy / 2 medium / 3 hard / 4 unfair. This changes the engine difficulty setting, not the selected Tiandixing script.

All four gold/XP multipliers share 0.15 increments from 0.15 to 4.95, plus explicit 1.00 default and 5.00 upper endpoint. Server accepts only those values. 42 addon tests pass, including upper limit, grid rejection, removed option rejection and native difficulty 4; real Workshop Tools compilation passed.

r11 replaces the r10 multiplier grid per user: 1, 1.15, 1.25, 1.35, 1.5, 1.75, 2, 2.5, 3, 4, 5. All four selectors and server allowlists match; 42 addon tests and real compilation passed.

## r12 false bot-count failure

User reported automatic pause and stationary bots after purchases. Live status proved 1 human + 10 bots for configured Radiant 5 / Dire 6, while addon had raised BotPopulate_incomplete_bot_count and deliberately disabled thinking/paused. bot_count only checked connection-state BOT whereas refresh_players already checked IsFakeClient; aligned both classifiers. Added regression for Tutorial fake clients reporting CONNECTED, plus actual fill method/expected/observed telemetry. 42 addon tests pass. New server session deployed; in-match movement still requires reconnection and new start. No UI change or client restart needed for this fix.

## r13 Tutorial activation parity

r12 live match reached playing with expected=12/observed=12 and no pause/error; user reports AI stationary. Original AI Fun calls SetBotThinkingEnabled again after AddBot and Tutorial:StartTutorialMode at pregame. These were missing in adaptation. Restored both, guarded once per match, with 10-second bot hero position samples for observed movement rather than assuming entry/purchases prove AI behavior. 42 tests pass, including Tutorial activation once. Default sv_cheats remains enabled per repeated user authorization; GameRules cheat-mode flag is distinct and not falsely reported as enabled.

## r14 chat cheats (explicit compatibility bridge)

User verified native -gold 100 had no effect with sv_cheats true. No verified setter for GC lobby allow_cheats was found. Added explicitly scoped addon player_chat handlers for -gold, -lvlup, -refresh, -respawn, default enabled via sv_cheats. Does NOT claim full native cheat mode or change GameRules:IsCheatMode. Uses engine player_chat identity, fixed command parsing, no arbitrary console execution, exact gold changes independent of income multiplier, bounded level gain. Records CHAT_CHEAT before/after. 42 addon tests pass; actual client chat effects require verification after reconnection.

## r15 in-match tools menu

At pregame/playing, the same left panel replaces setup controls with Player (reset/refresh/self +1000), Gold (all allied/enemy bots +1000 each), Levels (all allied/enemy bots +1 each). Setup controls stay hidden even when expanded. Team is resolved server-side from event-source player; bot operations filter IsFakeClient and exclude other humans. Fixed action allowlist, phase/handshake checks; gold bypasses income scaling; levels capped. MENU_CHEAT logs target counts. Reset revives and refreshes, and returns to fountain if GetTeamFountain is available. This remains an addon API implementation, not native lobby cheat mode.

42 addon tests passed with team targeting, excluded humans, invalid action/phase, and menu transition payload checks; real Windows compilation passed. r15 deployed; actual visual/button effects await user gameplay validation.

## r16 compact launcher and bot hero allocation

Live r15 showed expected/observed 9 bot player slots, but repeated AI_POSITIONS only listed one Luna. That hero moved and native Tiandixing callbacks reached 1024. All AddBot calls previously requested the same Luna; changed allocation to distinct standard heroes excluding already-selected player heroes. Added hero-entity count verification in addition to fake-client slot counts. This targets the observed missing-hero issue; new-match hero-count verification remains necessary. Hero allocation is now this addon's fixed pool rather than claiming Tiandixing chose every hero.

In-match menu defaults to a 60px Tools launcher to the right of the top scoreboard; expanded width245px with smaller buttons. Position uses Panorama reference coordinates and awaits visual confirmation at client's resolution. Real compilation and 42 addon tests passed, including unique hero allocation. r16 deployed.
