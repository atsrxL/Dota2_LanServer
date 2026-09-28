# Server Panorama compilation

Verified on CT270 (192.168.123.66), Ubuntu 24.04, 2026-09-20.
Official resourcecompiler.exe runs with Wine 9.0 and Xvfb. All four r24 Panorama inputs compiled with exit 0 and zero failed resources. Shader warnings occurred but did not prevent Panorama compilation. Client engine acceptance remains untested.

Steam depots: app 570, tools 381450 manifest 3664814097704453884; Windows engine 373303 manifest 9112253242025854370. Both downloads successfully reused the existing Steam login cache without password or Guard.

Persistent tool root: `/srv/steamcmd/linux32/steamapps/content/app_570/depot_381450`. Windows engine files were merged here; Linux game installation was not overwritten. Missing core/dota game metadata and VPK files link to the existing Linux installation. `assettypes_common.txt` must be readable by steam; root-owned mode 0700 caused a misleading missing-file error.

Compile only, as steam: `python3 /opt/dota2-lan-kit/tools/compile_panorama_wine.py` (options `--tools-root`, `--wineprefix`, `--log-dir`). Wine prefix is `/var/lib/dota2/wine-tools`. It compiles staged content only and fails unless every input reports `OK: N compiled, 0 failed`.

Full release, as root (stage and compile run as steam via runuser):

    python3 /opt/dota2-lan-kit/tools/release.py --version r25 --restart

Steps: stage → Wine compile → collect/validate → import into `addon/lan_dota/compiled` (old set kept as a backup) → build the Windows client package into `/opt/dota2-lan-kit/client-downloads` → restart (deploys the source on launch). Any failure stops before later steps. Without `--restart` the server keeps running the previous deployment; the panel overview shows source, deployed and client package hashes side by side.

Validated r24 artifacts: `/var/lib/dota2/artifacts/r24/lan-dota-r24-client.zip` and `lan-dota-r24-compiled.zip`, each with SHA256 sidecar. Headers, compiled manifest and staged UI source identity passed the existing addon_assets validation. Server/client game deployment has not been performed for r24.

The panel now remembers account names after verified authentication and uses the existing Steam cache for blank-password requests. Passwords remain excluded from configuration. Agent tests: 14 passed. Services dota-agent and dota-panel verified active.
