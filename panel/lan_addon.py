"""LAN addon lifecycle. Mutations run under Manager's existing single-job lock."""
from __future__ import annotations
import json
import os
import re
import secrets
import shutil
from pathlib import Path
from .common import Fault, Paths, atomic_json, now, read_json
from .addon_assets import ADDON_NAME, CLIENT_REVISION, COMPILED_FILES, MARKER, tree_inventory, source_identity, compiled_status
from .bot_audit import audit_scripts, instrument_scripts

DEFAULT_ADDON = {'schema': 1, 'enabled': False, 'launch_method': 'custom_command', 'probe_bots': False}


def validate_addon(raw):
    if not isinstance(raw,dict) or set(raw)-set(DEFAULT_ADDON): raise Fault('附加模式配置含未知字段')
    c = DEFAULT_ADDON | raw
    if type(c['schema']) is not int or c['schema'] != 1: raise Fault('附加模式配置版本无效')
    for k in ('enabled','probe_bots'):
        if type(c[k]) is not bool: raise Fault(k+' 必须为布尔值')
    if c['launch_method'] not in ('custom_command','addon_flag'): raise Fault('仅支持两个固定实验启动策略')
    return c


def lua_value(v):
    if v is None: return 'nil'
    if type(v) is bool: return 'true' if v else 'false'
    if type(v) is int: return str(v)
    if isinstance(v,str):
        return '"'+v.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n').replace('\r','\\r').replace('\t','\\t')+'"'
    if isinstance(v,list): return '{'+','.join(lua_value(x) for x in v)+'}'
    if isinstance(v,dict): return '{'+','.join('['+lua_value(k)+']='+lua_value(x) for k,x in sorted(v.items()))+'}'
    raise Fault('无法生成 Lua 配置')

class LanAddon:
    def __init__(self, paths: Paths, source: Path | None = None):
        self.paths = paths; self.source = source or Path(__file__).resolve().parents[1]/'addon'/ADDON_NAME
        self.root = paths.state/'lan-addon'; self.root.mkdir(mode=0o700,exist_ok=True)
        self.config_path = self.root/'config.json'; self.journal = self.root/'deploy-journal.json'
        self.target = paths.game/'game/dota_addons'/ADDON_NAME
        self.config = validate_addon(read_json(self.config_path, DEFAULT_ADDON.copy()))

    def save(self, raw):
        config = validate_addon(raw)
        if self.config_path.exists(): atomic_json(self.root/'config.previous.json',self.config)
        atomic_json(self.config_path,config); self.config = config
        return {'ok':True,'config':config,'notice':'下一次开服使用；不更改正在运行的比赛。'}

    def scan(self, bots, selected=None):
        selected = bots.validate_selection(selected if selected is not None else bots._selection().get('selected'))
        if not selected: raise Fault('先下载并选择天地星 1627071163 或 1573671599 的固定版本',409)
        if selected['item_id'] not in ('1627071163', '1573671599'): raise Fault('本实验仅接受天地星 1627071163 / 1573671599；实际兼容性仍需验证',409)
        report = audit_scripts(bots._version_path(selected['item_id'],selected['version'])/'scripts',selected)
        atomic_json(self.root/'audit.json',report)
        return report

    def _parents(self):
        cur = self.paths.game
        if cur.resolve()!=cur.absolute(): raise Fault('游戏路径含链接',409)
        for part in ('game','dota_addons'):
            cur=cur/part
            if cur.is_symlink(): raise Fault('附加模式目标父路径包含链接',409)
            cur.mkdir(exist_ok=True)

    def _managed(self, path):
        if path.is_symlink() or not path.is_dir(): raise Fault('附加模式目标无效',409)
        doc=read_json(path/MARKER)
        if not isinstance(doc,dict) or doc.get('files') != tree_inventory(path,True):
            raise Fault('附加模式目录未受管或被手工修改；保留文件，拒绝覆盖',409)
        return doc

    def recover(self):
        j=read_json(self.journal)
        if j is None: return
        if not isinstance(j,dict) or not re.fullmatch(r'[a-f0-9]{24}',str(j.get('transaction',''))) or type(j.get('had_target')) is not bool:
            raise Fault('附加模式恢复日志损坏；保留目录并人工检查',409)
        self._parents(); tx=j['transaction']
        old=self.target.parent/('.lan-dota-old-'+tx); new=self.target.parent/('.lan-dota-new-'+tx)
        for p in (old,new,self.target):
            if p.is_symlink(): raise Fault('恢复路径出现链接，禁止自动恢复',409)
        if old.exists():
            self._managed(old)
            if self.target.exists():
                if self._managed(self.target).get('transaction')!=tx: raise Fault('恢复发现外部替换，保留所有文件',409)
                shutil.rmtree(self.target)
            os.replace(old,self.target)
        elif j['had_target']:
            if not self.target.exists() or self._managed(self.target).get('transaction')==tx:
                raise Fault('恢复所需的旧目录丢失，停止自动开服',409)
        elif self.target.exists():
            if self._managed(self.target).get('transaction')!=tx: raise Fault('恢复发现未知目录',409)
            shutil.rmtree(self.target)
        if new.exists(): self._managed(new); shutil.rmtree(new)
        self.journal.unlink()

    def deploy(self, runtime=None, require_ui=False):
        self.recover(); self._parents()
        identity=source_identity(self.source); ui=compiled_status(self.source)
        if require_ui and not ui['ready']: raise Fault(ui['reason'],409)
        if self.target.exists(): self._managed(self.target)
        tx=secrets.token_hex(12); parent=self.target.parent
        new=parent/('.lan-dota-new-'+tx); old=parent/('.lan-dota-old-'+tx)
        try:
            shutil.copytree(self.source/'game',new)
            if ui['ready']:
                for rel in COMPILED_FILES:
                    dst=new/rel; dst.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copyfile(self.source/'compiled'/rel,dst)
            if runtime is not None:
                generated = {'schema':1,'session':runtime['session'],'client_revision':CLIENT_REVISION,
                    'source_sha256':identity['source_sha256'],'bot_available':bool(runtime.get('bot')),
                    'bot':runtime.get('bot'),'bot_globals':runtime.get('bot_globals',[])}
                (new/'scripts/vscripts/lan/generated.lua').write_text('return '+lua_value(generated)+'\n',encoding='utf-8')
            record={'schema':1,'transaction':tx,'installed_at':now(),**identity,'compiled_ui':ui['ready'],
                    'files':tree_inventory(new,True)}
            atomic_json(new/MARKER,record)
            atomic_json(self.journal,{'transaction':tx,'had_target':self.target.exists()})
            if self.target.exists(): os.replace(self.target,old)
            os.replace(new,self.target)
            # The target marker is the commit record. Keep one known-good prior
            # deployment, never auto-delete unrecognized or edited backups.
            self.journal.unlink()
            backup=self.root/'previous-deployment.json'
            last=read_json(backup,{})
            if old.exists(): atomic_json(backup,{'directory':old.name,'transaction':tx})
            previous=last.get('directory')
            if isinstance(previous,str) and re.fullmatch(r'\.lan-dota-old-[a-f0-9]{24}',previous) and previous!=old.name:
                p=parent/previous
                if p.exists():
                    try: self._managed(p)
                    except Fault: pass
                    else: shutil.rmtree(p)
            return {k:v for k,v in record.items() if k!='files'}
        except Exception:
            if not self.journal.exists() and new.exists(): shutil.rmtree(new)
            raise

    def prepare(self,bots,override=None,reuse=False,prior=None):
        c=validate_addon(prior['config'] if reuse and prior else self.config)
        if not c['enabled']: return None,None
        # Fail BEFORE modifying an existing Bot deployment when UI is absent.
        ui=compiled_status(self.source)
        if not ui['ready']: raise Fault(ui['reason'],409)
        if reuse and prior and ui['source_sha256']!=prior['source_sha256']:
            raise Fault('崩溃重试发现附加模式源码已变；拒绝静默换版本',409)
        self.recover(); self._parents()
        if self.target.exists(): self._managed(self.target)
        selected=bots.validate_selection(override if reuse else bots._selection().get('selected')) if c['probe_bots'] else None
        report=self.scan(bots,selected) if selected else None
        session=secrets.token_hex(16)
        def observer(root, spec):
            from .tiandixing import adapt
            adapt(root, spec)
            instrument_scripts(root, spec, session, report)
        if not selected: observer = None
        spec=bots.prepare_launch(override=selected,use_override=True,observer=observer)
        runtime={'name':ADDON_NAME,'session':session,'config':c,'launch_method':c['launch_method'],
                 'source_sha256':ui['source_sha256'],'client_revision':CLIENT_REVISION,
                 'bot':spec,'bot_globals':report['bot_globals'] if report else []}
        self.deploy(runtime,require_ui=True)
        atomic_json(self.root/'last-launch.json',runtime)
        return spec,runtime

    def status(self, game=None):
        try: ui=compiled_status(self.source)
        except (Fault,OSError) as exc: ui={'ready':False,'reason':str(exc)}
        result={'config':dict(self.config),'source':ui,'audit':read_json(self.root/'audit.json'),
                'recovery_required':self.journal.exists(),
                'deployment':None,'runtime':None,'client_revision':CLIENT_REVISION}
        if self.target.exists():
            try: result['deployment']={k:v for k,v in self._managed(self.target).items() if k!='files'}
            except Fault as exc: result['deployment_error']=str(exc)
        if game is not None and game.addon_telemetry is not None:
            result['runtime']=game.addon_telemetry.snapshot(game.running())
        result['notice']='准备界面是自制 Panorama，不是官方 Lobby。天地星为实验原生 Bot 路线；没有模拟 GetBot，没有重写 AI。'
        return result
