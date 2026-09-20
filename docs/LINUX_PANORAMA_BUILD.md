# Server Panorama compilation

Verified on CT270 (192.168.123.66), Ubuntu 24.04, 2026-09-20.
Official resourcecompiler.exe runs with Wine 9.0 and Xvfb. All four r24 Panorama inputs compiled with exit 0 and zero failed resources. Shader warnings occurred but did not prevent Panorama compilation. Client engine acceptance remains untested.

Steam depots: app 570, tools 381450 manifest 3664814097704453884; Windows engine 373303 manifest 9112253242025854370. Both downloads successfully reused the existing Steam login cache without password or Guard.

Persistent tool root: `/srv/steamcmd/linux32/steamapps/content/app_570/depot_381450`. Windows engine files were merged here; Linux game installation was not overwritten. Missing core/dota game metadata and VPK files link to the existing Linux installation. `assettypes_common.txt` must be readable by steam; root-owned mode 0700 caused a misleading missing-file error.

Run as steam: `python3 /opt/dota2-lan-kit/tools/compile-panorama-wine.py`. Wine prefix is `/var/lib/dota2/wine-tools`. The script builds staged content, not automatically synchronized repository files. Stage current sources and validate their hashes before collecting results.

Validated r24 artifacts: `/var/lib/dota2/artifacts/r24/lan-dota-r24-client.zip` and `lan-dota-r24-compiled.zip`, each with SHA256 sidecar. Headers, compiled manifest and staged UI source identity passed the existing addon_assets validation. Server/client game deployment has not been performed for r24.

The panel now remembers account names after verified authentication and uses the existing Steam cache for blank-password requests. Passwords remain excluded from configuration. Agent tests: 14 passed. Services dota-agent and dota-panel verified active.
