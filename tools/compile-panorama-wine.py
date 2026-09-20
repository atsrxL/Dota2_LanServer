from pathlib import Path
import subprocess,os
r=Path("/srv/steamcmd/linux32/steamapps/content/app_570/depot_381450")
env=os.environ.copy();env.update(WINEPREFIX="/var/lib/dota2/wine-tools",WINEDEBUG="-all")
for name in ["layout/custom_game/custom_ui_manifest.xml","layout/custom_game/lan_setup.xml","scripts/custom_game/lan_setup.js","styles/custom_game/lan_setup.css"]:
 cmd=["xvfb-run","-a","/usr/lib/wine/wine64",str(r/"game/bin/win64/resourcecompiler.exe"),"-nop4","-f","-game","Z:"+str(r/"game/dota"),"-i","Z:"+str(r/"content/dota_addons/lan_dota/panorama"/name)]
 p=subprocess.run(cmd,cwd=r/"game/bin/win64",env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=120)
 (Path("/var/lib/dota2")/("compile-"+Path(name).name+".log")).write_text(p.stdout)
 print(name,"EXIT",p.returncode,p.stdout[-2300:],flush=True)
 if p.returncode:raise SystemExit(p.returncode)
