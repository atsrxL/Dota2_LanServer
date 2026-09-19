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

## Free courier fix and pending neutral acceleration

Restored original AI Fun SetFreeCourierModeEnabled(true) during game-mode initialization. This enables standard free courier spawning, not the removed fast courier modifier. 42 addon tests passed with explicit initialization assertion; deployed server-side, gameplay spawning awaits confirmation.

Requested neutral acceleration: tier1 default, tiers2–5 at 5/10/15/20 minutes, tier5 recrafting at25. Current build's neutral_items.txt has neutral_tiers/start_time and madstone_limits/madstone_no_limit_time=70:00, no separate recraft time. Public Lua API lacks a runtime schema setter. A setup-panel switch remains unimplemented pending proven schema load/reload and recraft gating; no dummy control added and madstone limit not misrepresented as a proven recraft-time field.

## Fixed accelerated neutral schema

User chose fixed defaults instead of a runtime switch. Added scripts/npc/npc_neutral_items_custom.txt, derived from this installed build's neutral_items.txt; only changes are tier2–5 start_time=5:00/10:00/15:00/20:00 and madstone_no_limit_time=25:00 (was70:00). Tier1 remains0:00; all pools, costs, enhancements unchanged. Synced .98 game addon and managed server addon. The 25-minute field removes the madstone cap; it is not an independently documented recraft-time setter. Actual tier UI/recraft behavior still requires gameplay verification. Source schema is Valve-derived local deployment data, not original project-authored content.

## r17 personal Tiandixing server and match tools (2026-09-18)

Archived the Bot management HTML/JS and former UI smoke fragment under docs/archive/bot-panel. A complete pre-change source ZIP is retained outside Git in deployment-1.3.0/bot-management-before-r17.zip. CT270 backup: /root/agent.backup/dota-r17-20260918/pre-r17.tar.gz (code, addon and bot deployment/library state; no Steam cache).

Removed Bot navigation, served bots.js, management controls and console population. CT270 bot-library/fixed-policy.json pins 1573671599 / ea5bacf5e672376dc1514f0758e7def17c48b28b8bf4a35a83c1308795f7f438. Bot mutation jobs now return403 under the policy; startup rejects another selection or disabled addon/Bot path. The immutable library/transaction code stays for deployment and rollback. Live HTTP confirmed controls absent and bot_default returns403.

Extended addon max_players from10 to24 to match the existing team1–12 choices. Version-scoped deployment-only Tiandixing adapter extends lane tables after slot5, cycles the five selection roles, expands only loops that enumerate GetTeamMember, and removes transient spawn-invulnerability checks from top-level script load guards (per-frame checks retained). Workshop originals are unchanged. New BOT_ACTOR telemetry identifies actual pid/hero/callback; this is needed to verify every extra bot rather than infer script use from movement. These fixes address observed code restrictions; >5-per-team real gameplay remains pending client validation.

Runes use default Dota spawn logic plus a spawn filter allowing only dota_item_rune_spawner_powerup (the standard river spawners). Bounty/XP/unknown spawners are rejected; first decision per spawner is logged. No manual rune timer or extra jungle spawning. Actual map/filter events await the next match.

Reset is a separate compact button next to Tools, visible even when collapsed. Tools add eight fixed self-hero ability buttons: death_prophet_witchcraft, winter_wyvern_eldwurms_edda, silencer_brain_drain, tinker_eureka, beastmaster_inner_beast, razor_unstable_current, bloodseeker_thirst, faceless_void_distortion_field. All eight names are present in this build's VPK hero definitions. Added at maximum level, existing abilities are left intact; invalid/full/engine failures return feedback without pausing the game. Native ability dependencies and actual cross-hero effects remain to be tested.

BAT buttons change the player's selected hero by±0.1 seconds (0.1–10 safety range), or restore the base attack time captured at first hero initialization. Uses GetBaseAttackTime/SetBaseAttackTime directly, with per-hero stored baseline. Existing authenticated event source, handshake, phase and sv_cheats checks remain; no arbitrary command or ability input is accepted.

Validation: 210 tests passed,28 existing warnings (forkpty27/duplicate ZIP fixture1). Added self-target/allowlist/duplicate/error/BAT/reset/rune mock regressions, adapter source regressions, fixed policy tests and updated archived-control expectations. All adapted third-party Lua syntax checked without local execution. Real Windows Workshop Tools compile passed; source SHA0761116f29f72a2e90f5e88e67b58065f0f2566ea2bafb61b9a8a27ad556bd15. Client ZIP r17 SHA9842120d78f90905ae620163ca3fb95ac0ea25eb4ed0c0bb6b1b11205f1475f5 installed on .98 and .180,17 installed files each hash-verified. CT270 new session83be1ab955e753af6840529904b30a74 boots with sv_cheats=true and no addon error; waiting for client6v6 verification. No public push.

### r17b live correction

The user entered5v12 during r17 validation. Live runtime raised `GetBaseAttackTime called with 1 arguments - expected 2`, despite old public declarations showing a parameterless method. Updated server calls to `GetBaseAttackTime(false)` and guarded baseline capture so an API mismatch cannot pause initialization. Subsequent button/hero effect is still pending a new connection; mocks explicitly require the argument.

A direct inspection found the installed 1573671599 BotLib lacks earthshaker, puck, pudge, storm_spirit, vengefulspirit and windrunner, all present in the former24-hero fixed pool. r17 logs had native generic script load failures. The version-scoped adapter now derives a53-hero pool from actual BotLib/hero_*.lua files and passes it through the generated bot snapshot; AddBot uses that pool. This is a concrete missing-script cause distinct from the five-entry lane restriction. No fake fallback AI or copied default hero scripts were added.

r17b:44 targeted addon/adapter tests pass after the correction (prior complete suite210 passed). CT270 session c35b8dafad4c42e3c09688f9189cb326, source SHA559134c16e30faed94506228e9eb225fd3b4a0a290364fae782a1c6a12d1b74b, initial boot errors[]. Server backup also at /root/agent.backup/dota-r17b-20260918/pre-r17.tar.gz. Client ZIP SHA c83a4f23fd2a8f70575c04f22283e6d74ad21108eb751b179636e7f07cf61886; .98 and .180 each17 files verified. UI unchanged from r17 actual compilation. Reconnection requested; >5-per-team callbacks, actual BAT buttons, all cross-hero passive effects and rune events remain NOT_RUN for r17b until the next match. Earlier r17 errors are not omitted or presented as a pass.

## r18 split difficulty, reduced options, icon launcher and Bot naming

User requested independent Radiant/Dire native difficulty (0–4), team counts4–12 inclusive, no starting-level controls, no AI protection/anti-diving, and unconditional pause permission. Removed those controls, option keys, validation and modifier effects; removed allow_pause as a configurable key and always calls SetPauseEnabled(true). There are no remaining boolean dropdowns in the setup panel. Per-hero SetBotDifficulty applies the selected team's value at npc_spawned and reconciles at the regular hero tick, with BOT_DIFFICULTY telemetry; removed global difficulty console commands which would overwrite both teams.

Reset/Tools are icon-only in-game. Uses verified installed refresh/settings textures; located at left146px/top0, immediately after the standard native menu bar's three30px buttons with8px margins. Hover tooltips remain. Setup retains its text toggle. Actual in-game position needs client visual verification; this is based on this build's extracted dota_hud_menu_buttons CSS, not a screenshot claim.

Removed the erroneous24-slot precheck from skill addition. Native GetAbilityByIndex can expose populated/placeholder slots; it is no longer used as an artificial lock. AddAbility is attempted directly with the fixed eight-name allowlist, duplicate check and guarded engine failure handling. Mock includes occupied indexes and successful addition.

User clarified the remaining >5 AI concern was different names/display. Session c35b8dafad4c42e3c09688f9189cb326 has native Tiandixing ItemPurchaseThink and AbilityLevelUpThink for all16 bots (pid1–16), with skill callbacks on extra slots; no recent native script runtime errors found in retained logs. This proves the extra bots execute these callbacks, not that every gameplay behavior is identical. Root cause for naming: X.GetRandomNameList generated only5 names. Deployment-only adapter now generates up to12 names per team from a copied original star pool, leaving the original table intact. Also corrected GetOutfitType's original five-player loop/default-carry fallback: all slots are considered and the five outfit roles cycle. BOT_SETUP telemetry adds actual team/roster/lane/next-purchase context.

46 addon/adapter tests pass (Lua and Panorama mocks included). Real Windows compilation completed with0 failures. r18 source SHA3ded55f0a258f565afbf5ac34422dba083a29a592a2c7d1198f996581712a7d7. Client ZIP SHA8475b0018cc91e5345286a406df1f27e7c715f53d86690bb768eaff46861184c, both .98 and .180 installed17 files and verified every hash. CT270 session ceaba2d6b7869b2dada37d46d677bd22 boots errors[]. Native setter effects, new name display and exact icon placement await a new match; AddAbility effects still need actual button validation after removing the precheck. Old slot counter error was application logic, not a proven native engine limit.

Snapshot rotation keeps server r17b and r18 snapshots; r17/pre-r17.tar.gz was rotated after checking both newer archives. Original removed UI remains under docs/archive/bot-panel and full pre-change source ZIP outside Git. Client snapshots likewise retain the newest two known agent-created backups for this addon. No public push.

## r19 random Bot draft (staged for next match)

Replaced sequential hero allocation with a Fisher–Yates shuffle using engine RandomInt, applied once to a private copy of the verified Tiandixing hero pool at strategy-time fill. Excludes every already-selected hero and deduplicates the input; both teams draw from the same shuffled pool without replacement. Missing verified pool now fails explicitly instead of using the old unsupported static fallback. Preflight capacity check occurs before AddBot; BOT_DRAFT logs each actual team/hero selection. Repeated fill ticks cannot redraw or add duplicates.

46 related tests pass, including alternate RNG outcomes, unchanged source pool, player hero exclusion, unique23-bot draw from53 supported heroes and once-only8-bot population. These are mock tests; the next live match's randomized draft is not yet observed.

Only addon source staged to CT270 /opt/dota2-lan-kit/addon. The user's ongoing match continues with its original deployment/session; next manual server start/restart applies r19. No current-match hero replacement, no agent restart, no UI changes or recompilation. Source SHA294a6d5ae2e0cafe9508e75794e6fc1d4f7a6cee69e193c8973a6a3ca9c59157; staged source and compiled manifest report ready. Backup /root/agent.backup/dota-r19-source-20260918/before-r19.tar.gz. Existing crash-retry source-lock behavior remains: manual restart is the transition to the new source.

Client ZIP r19 SHA3953966aa3e77af633e724f8aeba507a4d1539fd588dfd388819fceac5fb8b31 is packaged for future installations; current clients do not need a UI update for server-side Bot selection. Public push not performed.


## r20 — personal-match lifetime and setup defaults (2026-09-18)

- Group Radiant/Dire controls by setting: difficulty, gold multiplier, XP multiplier, starting gold, team size.
- Defaults: Radiant Easy (1), Dire Unfair (4), respawn 30%, maximum level 50, pregame 30 seconds. Hidden selection/buyback controls use server defaults of 60 seconds each. Add 30% to the server respawn allowlist.
- `lan.lifecycle` disables native disconnect surrender and empty-server hibernation; keeps native pause enabled. The pause-force, pause-limit and all-disconnected timers use 2147483647 seconds (about 68 years). This is a practical timeout bypass, **not a verified native unlimited sentinel**; undocumented 0/-1 semantics are deliberately not assumed. Normal Ancient victory remains unmodified; there is no addon unpause or disconnect-end call.
- Real Windows Workshop Tools compilation: changed JS 1 compiled / 0 failed; remaining 3 resources unchanged/skipped. Both .98 QGA and .180 SSH installed and SHA-verified 19 client files.
- Client package `lanlab-client-r20.zip` SHA256 `e13357264f778c0ab5de0b7cc47ed28c60da384d8a84a36193beb1df3861cd04`; UI SHA256 `5eadc20d4a1f1327be7fcc75e8eca3fb1a3141e55d0a38e3c4f2b2922ab293d5`; addon source SHA256 `0edaf2cc692ee8980aaef048a67247ca24f4ac2fdfd893669e3e5530f663e980`.
- Server restarted, session `978014dfc8fbb170632708b801a668c9`. Real LIFECYCLE log reads back both booleans false, pause allowed true, all 3 timers `2.1474836e+09`; server woke from hibernation. Runtime defaults match requested values; no addon errors. Waiting for a client connection. r19 random drafting is included.
- Backup: `/root/agent.backup/dota-r20-source-20260918/before-r20.tar.gz`; client backups .98 `20260918-215742`, .180 `20260918-215726`.
- Validation boundaries: automated tests exercise defaults, neighboring controls, hidden controls, and disconnect/postgame transitions using mocks. Actual >5 minute pause, human disconnect during a running bot match, Ancient destruction, and refreshed in-game UI remain user/client acceptance checks; startup settings alone do not prove those behaviors.
- Final validation: `bash scripts/test.sh` passed **212 tests** (28 existing fixture/runtime warnings); package CRC and every source-file SHA256 passed. Client backup rotation retains the two most recent agent snapshots on each PC.


## Native dota_create_ability investigation (2026-09-18)

User tested `dota_create_ability bloodseeker_thirst`: no output and no effect. Current build command dump registers it as `gamedll client_can_execute`, so command existence/client permission alone does not prove availability.
Read-only inspection of build25329722 Linux libserver.so: command-string XREF at RVA0x580ddc8 registers callback RVA0x57b8ab0. Callback first calls gate RVA0x5057d10 and returns silently on false, before parsing arguments. The gate references `sv_cheats`, but also checks lobby/environment state before its later sv_cheats fallback. Gate path: primary lobby -> fallback lobby collection -> cached environment check; if no lobby and environment check returns true, returns false immediately.
Read-only `/proc/24946/mem` inspection during session978014dfc8fbb170632708b801a668c9 found primary lobby absent, fallback lobby collection count0, environment check initialized1/result1. Live addon reports playing/errors[]; previous BOOT sv_cheats=true/GameRules cheat=false. This supports the native silent-rejection diagnosis for this dedicated no-GC-lobby environment; this is not a skill-slot limit diagnosis. No binary patch, process-memory write, command shadowing, server restart, or client resource change was performed. Exact symbols of the stripped environment check were not available; do not claim a verified native allow_cheats setter or universal behavior across builds. Existing tool-menu AddAbility implementation remains the supported path on this deployment.


## r21 — typed ability names in match tools (2026-09-19)

Added native Panorama TextEntry (paste supported) and add button under the ability section; Enter submits too. Existing eight shortcut buttons remain. A separate fixed `self_add_ability` action carries `ability_name` as data through the existing engine-resolved player identity/handshake/phase/sv_cheats checks. Only the caller's hero is targeted. Trim whitespace, bound input, accept only lowercase internal names; check GetAbilityKeyValuesByName when available, detect duplicates, and catch AddAbility failures. Added skills use their maximum level. No console/script evaluation or native command shadowing.

Validation: 212 tests passed (28 existing warnings), including typed addition, duplicates, nonexistent names, non-string input, command-like input, length and handshake checks plus UI button/Enter events. Windows Workshop Tools compiled XML/JS/CSS without errors. .98 installed and hash-verified 19 files; backup C:/root/agent.backup/dota-lan-client-20260919-123231. .180 was unreachable (SSH timeout/host down): **not installed there**. .98 backup rotation subsequently failed at Znas SSH transport and remains pending (old known backup205857); installation itself completed successfully before that failure.

Client ZIP `lanlab-client-r21.zip` SHA256 bcfbab6c3b05f6731c13a365ac447970c0313b1e2332ba404495716ad61abb09; UI SHA aa1be39b2e06fc5de78d5ea8434cad078316a608dcf1bf3bf54ab706806a47b1; source SHA a5c579a13a143b36f00c8e68c205468b420d77a380ef398c40ac6317417bf3a9. Server backup /root/agent.backup/dota-r21-source-20260919/before-r21.tar.gz; new session647e4c5cbd44e22a0611c58a962522b2 booted without addon errors, waiting_engine, no connected players. Actual in-game paste/add interaction pending client acceptance. No public push.


## r22 — adaptive per-bot income (2026-09-19)

Enabled server-side comeback module for both teams, per bot/player slot, reset each match. Each actual hero death adds +0.1 XP multiplier and +0.2 gold multiplier, additively on the configured baseline. An enemy hero kill credited to the bot (including player-owned attackers) clears its death stacks and fractional remainders and sets BOTH baselines to exactly1x, regardless of setup baseline. Subsequent deaths build from1x. Assists, allied denies, non-heroes, illusions/clones/tempest doubles and reincarnation do not trigger the relevant counters. Human rewards are unchanged. No dynamic cap was requested; setup's5x selection cap remains only a baseline selection cap.

Existing positive income filters now route through lan.bot_comeback; negative gold/spending untouched. Fractional remainder per bot/resource preserves bonuses on frequent small income ticks. Fixed tool-menu gold and levels use their existing direct APIs and do not scale. BOT_COMEBACK and BOT_COMEBACK_RESET record state changes. This does not change Tiandixing AI logic. No UI changes/recompile needed; client r21 remains compatible. Future installation package updated to r22 (SHA02d3ccab452225c551458142e6ac30ac9f6cfafb965449d25edb633747867289).

Mocks cover independent bots, unchanged humans, configured baselines, repeated death, negative rewards, fractional ticks, invalid/illusion/reincarnation victims, enemy-kill reset to1x, post-reset stacking, ally denial, non-hero kills, and fresh match state. Actual in-match kill/death income acceptance remains pending.

Deployment: server restarted with no connected players; session 1311029042beb7f2f8c0f69b798c206e, source SHA b48a9fd460c995df46082c91d7bdd1297e3c16d084c517c13a4eeeab4f6fd667, no addon boot errors. Full suite212 passed (28 existing warnings). Backup /root/agent.backup/dota-r22-source-20260919/before-r22.tar.gz. No claim of actual kill/death acceptance yet.

2026-09-19 .180 follow-up: SSH online on DESKTOP-98X3D; r22 client package installed to D:/steamC/steamapps/common/dota 2 beta, all20 game files SHA256 verified. Backup C:/root/agent.backup/dota-lan-client-20260919-163357; retained it and20260918-215726, removed known agent backup20260918-205855. Includes r21 typed ability UI. Client restart/reconnect required to discard cached Panorama.
