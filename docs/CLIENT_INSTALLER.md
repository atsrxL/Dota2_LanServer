# Windows client downloads

The panel exposes a dedicated Windows client resources page. Fixed endpoints:
/api/client-resources and /api/client-download?kind=exe (or zip).
Only the two named artifacts under /opt/dota2-lan-kit/client-downloads are served.
Downloads verify size, SHA-256 and source identity against the installed server source.

Build on the server with Ubuntu nsis installed:

    python3 tools/build_windows_client.py --source /opt/dota2-lan-kit/addon/lan_dota --output /var/lib/dota2/client-release --version r23

The builder validates actual compiled resources before packaging. NSIS creates a Unicode
Windows executable containing only project client resources and the installer script.
Windows PowerShell 5.1 reads the script as UTF-8 with BOM. The installer detects Steam
from the registry, resolves libraryfolders.vdf, accepts an explicit Dota directory,
requires Dota to be closed, backs up overwritten files under LOCALAPPDATA/Dota2LAN/Backups,
checks hashes before/after copying and attempts rollback on copy failure.

2026-09-20: built on CT270; published r23 to match the installed server source.
r24 is compiled but remains separate until coordinated server/client deployment.
Live HTTP EXE download hash matched the release manifest. Chrome overview and client
page navigation verified. Full code suite: 216 passed, 29 existing warnings.
Native Windows installation and subsequent Dota connection are not yet tested.

Panel cleanup removes duplicate overview task/addon/getting-started cards and static
explanatory paragraphs. Steam account editing remains only on SteamCMD; saving server
configuration preserves that account value. Functional errors and maintenance/input
prompts remain visible. Detailed help remains accessible separately.
