# Installed AI Fun UI adaptation

Source: user's Windows Workshop item 956357541, DOTA2 AI Fun 12v12, publish_data timestamp 1773370668. Read-only extraction from 956357541.vpk, preserved outside repository at deployment-1.3.0/fun-reference.zip. Original subscription untouched.

Adapted actual game_mode.js AddDropDown implementation (dynamic option registration with AddOption, selection via oninputsubmit) and option-row CSS from custom_loading_screen.css. Removed localization dependency for these few labels, Tools overrides, multiplayer broadcasts/voting, Fun options, external links and map artwork. This is a scoped UI adaptation, not a full fork of its gamemode or AI implementation. Local personal deployment; upstream licensing was not present in the extracted subset, no public push performed.

Single-player confirm uses existing authenticated lan_action source resolution with new solo_start action, validated option allowlist, host/revision/one-human checks, automatic Radiant assignment, readiness and guarded start. Uses existing selected Tiandixing 1573671599 and one-shot BotPopulate route. No client-supplied PlayerID authorization.

42 addon tests pass including solo duplicate/start/count validation and adapted dynamic-control mock. Real Workshop Tools compilation passed, r8 deployed to .98 and CT270. Actual r8 visual/AI behavior still requires client verification. No claim that neutral tier unlock configuration is implemented.
