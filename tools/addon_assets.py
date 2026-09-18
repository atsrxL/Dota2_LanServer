#!/usr/bin/env python3
"""Offline Workshop Tools source staging, compiled UI import and client export.

No network, no Steam credentials, no compiler imitation. Default staging/import
is dry-run. Collect/export only read known files and create a NEW output ZIP.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
import time
import zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from panel.addon_assets import (ADDON_NAME,CLIENT_REVISION,COMPILED_FILES,MAX_ASSET_BYTES,
    source_identity,tree_inventory,compiled_status,validate_resource)
from panel.common import Fault
SOURCE=Path(__file__).resolve().parents[1]/'addon'/ADDON_NAME
STAGE_MARKER='.lanlab-source-stage.json'


def no_links(path: Path) -> Path:
    path=path.absolute()
    if path.resolve()!=path: raise Fault('路径中包含链接；请用真实目录',409)
    return path


def write_zip(target: Path, files: dict[str,bytes]):
    target=no_links(target)
    if target.exists(): raise Fault('输出文件已存在；选择新文件名，不覆盖',409)
    target.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED) as z:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo(name); info.create_system=3
            info.external_attr=(stat.S_IFREG|0o644)<<16
            z.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED)
    target.with_suffix(target.suffix+'.sha256').write_text(hashlib.sha256(target.read_bytes()).hexdigest()+'  '+target.name+'\n')
    return {'output':str(target),'files':len(files),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}


def stage(source: Path, dota: Path, apply=False, replace_managed=False):
    source=no_links(source);dota=no_links(dota); identity=source_identity(source)
    if not (dota/'game').is_dir() or not (dota/'content').is_dir():
        raise Fault('--dota-root 应为包含 game 和 content 的 Workshop Tools Dota 目录',409)
    destinations=[]
    for folder in ('game','content'):
        dest=no_links(dota/folder/'dota_addons'/ADDON_NAME)
        if dest.exists():
            marker=dest/STAGE_MARKER
            if not replace_managed or not marker.is_file(): raise Fault('目标已存在；不覆盖。受管目录可用 --replace-managed',409)
            old=json.loads(marker.read_text())
            for name,meta in old.get('files',{}).items():
                p=dest/name
                if not p.is_file() or p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest()!=meta['sha256']:
                    raise Fault('Workshop Tools 源码被修改；先保存并合并修改',409)
            if not old.get('files'): raise Fault('原始源码清单无效',409)
        destinations.append((folder,dest))
    if not apply: return {'dry_run':True,'destinations':[str(x[1]) for x in destinations],**identity}
    backups=[]
    for folder,dest in destinations:
        dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():
            backup=dest.with_name(dest.name+'.source-backup-'+str(time.time_ns()))
            os.replace(dest,backup);backups.append(str(backup))
        shutil.copytree(source/folder,dest)
        (dest/STAGE_MARKER).write_text(json.dumps({'schema':1,**identity,'files':tree_inventory(source/folder)},indent=2))
    return {'dry_run':False,'backups':backups,**identity,
        'next':'在 Workshop Tools 编译四个 Panorama 资源，collect 只收集不执行编译。'}


def collect(source: Path,dota: Path,output: Path):
    identity=source_identity(source)
    content=no_links(dota/'content/dota_addons'/ADDON_NAME)
    # Verify sources actually staged; no guess from filename or compiled mtime.
    for name,meta in tree_inventory(source/'content').items():
        p=content/name
        if not p.is_file() or p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest()!=meta['sha256']:
            raise Fault('Tools 中 UI 源码与交付源码不同；重新 stage/编译或先合并修改',409)
    game=no_links(dota/'game/dota_addons'/ADDON_NAME)
    files={};manifest={}
    for name in COMPILED_FILES:
        p=no_links(game/name)
        if not p.is_file() or p.stat().st_size>16*1024*1024: raise Fault('编译资源缺失或过大: '+name,409)
        data=p.read_bytes();validate_resource(data)
        files[name]=data;manifest[name]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    files['asset_manifest.json']=json.dumps({'schema':1,'client_revision':CLIENT_REVISION,
        'ui_source_sha256':identity['ui_source_sha256'],'files':manifest,
        'note':'真实 Tools 输出的收集记录；头检查不是引擎验收'},indent=2,ensure_ascii=False).encode()
    return write_zip(output,files)


def import_assets(source: Path,archive: Path,apply=False):
    source=no_links(source);target=source/'compiled'
    allowed=set(COMPILED_FILES)|{'asset_manifest.json'}
    with tempfile.TemporaryDirectory() as temp:
        stage_root=Path(temp).resolve()/'addon';shutil.copytree(source/'game',stage_root/'game');shutil.copytree(source/'content',stage_root/'content')
        out=stage_root/'compiled';out.mkdir()
        with zipfile.ZipFile(archive) as z:
            infos=z.infolist();names=[i.filename for i in infos]
            if len(names)!=len(set(names)) or set(names)!=allowed: raise Fault('资源 ZIP 文件集合不符或有重复',409)
            total=0
            for item in infos:
                mode=item.external_attr>>16
                if item.flag_bits&1 or (stat.S_IFMT(mode) not in (0,stat.S_IFREG)) or item.file_size>16*1024*1024:
                    raise Fault('资源 ZIP 包含链接、加密、特殊或过大文件',409)
                total+=item.file_size
                if total>MAX_ASSET_BYTES: raise Fault('资源 ZIP 超出总量限制',409)
                p=out/item.filename;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(item))
        status=compiled_status(stage_root)
        if not status['ready']: raise Fault(status['reason'],409)
        backup=None
        if apply:
            if target.exists():
                if not compiled_status(source)['ready']: raise Fault('现有 compiled 已修改或无效；人工备份后再导入',409)
                backup=source.parent/(source.name+'.compiled-backup-'+str(time.time_ns()))
                os.replace(target,backup)
            try: shutil.copytree(out,target)
            except Exception:
                if target.exists(): shutil.rmtree(target)
                if backup: os.replace(backup,target)
                raise
        return {'dry_run':not apply,'backup':str(backup) if backup else None,**status}


def client_export(source: Path,output: Path):
    status=compiled_status(source)
    if not status['ready']: raise Fault(status['reason'],409)
    files={}
    for name in tree_inventory(source/'game'):
        files['game/dota_addons/'+ADDON_NAME+'/'+name]=(source/'game'/name).read_bytes()
    for name in COMPILED_FILES:
        files['game/dota_addons/'+ADDON_NAME+'/'+name]=(source/'compiled'/name).read_bytes()
    files['LANLAB_CLIENT.json']=json.dumps({'schema':1,**source_identity(source),
        'note':'只含本项目资源；无天地星包、Steam凭据或服务端会话。关闭游戏后解压到 Dota 根目录。'},indent=2,ensure_ascii=False).encode()
    return write_zip(output,files)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=SOURCE)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('stage');p.add_argument('--dota-root',type=Path,required=True);p.add_argument('--apply',action='store_true');p.add_argument('--replace-managed',action='store_true')
    p=sub.add_parser('collect');p.add_argument('--dota-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p=sub.add_parser('import');p.add_argument('--archive',type=Path,required=True);p.add_argument('--apply',action='store_true')
    p=sub.add_parser('client-package');p.add_argument('--output',type=Path,required=True)
    sub.add_parser('status')
    a=parser.parse_args()
    try:
        if a.command=='stage': result=stage(a.source,a.dota_root,a.apply,a.replace_managed)
        elif a.command=='collect': result=collect(a.source,a.dota_root,a.output)
        elif a.command=='import': result=import_assets(a.source,a.archive,a.apply)
        elif a.command=='client-package':result=client_export(a.source,a.output)
        else:result=compiled_status(a.source)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (Fault,OSError,ValueError,zipfile.BadZipFile) as e:
        print('ERROR: '+str(e),file=sys.stderr);return 1
    return 0
if __name__=='__main__': raise SystemExit(main())
