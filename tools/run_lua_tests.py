#!/usr/bin/env python3
"""Run our own Lua test fixtures, never downloaded Workshop code.

Uses a local Lua 5.4 shared library for source syntax and mock-engine tests.
This is NOT the Dota VM and provides no real engine compatibility verdict.
"""
from __future__ import annotations
import argparse
import ctypes as C
import ctypes.util
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def run_lua(source: str,name='test',execute=True):
    lib=ctypes.util.find_library('lua5.4')
    if not lib: raise RuntimeError('需要本地 liblua5.4（仅开发测试），不用于生产服务。')
    lua=C.CDLL(lib)
    lua.luaL_newstate.restype=C.c_void_p
    lua.luaL_openlibs.argtypes=[C.c_void_p]
    lua.luaL_loadbufferx.argtypes=[C.c_void_p,C.c_char_p,C.c_size_t,C.c_char_p,C.c_char_p];lua.luaL_loadbufferx.restype=C.c_int
    lua.lua_pcallk.argtypes=[C.c_void_p,C.c_int,C.c_int,C.c_int,C.c_ssize_t,C.c_void_p];lua.lua_pcallk.restype=C.c_int
    lua.lua_tolstring.argtypes=[C.c_void_p,C.c_int,C.POINTER(C.c_size_t)];lua.lua_tolstring.restype=C.c_char_p
    lua.lua_close.argtypes=[C.c_void_p]
    state=lua.luaL_newstate()
    if not state:raise MemoryError('Lua allocation failed')
    try:
        lua.luaL_openlibs(state);data=source.encode()
        status=lua.luaL_loadbufferx(state,data,len(data),name.encode(),b't')
        if not status and execute:status=lua.lua_pcallk(state,0,0,0,0,None)
        if status:raise AssertionError((lua.lua_tolstring(state,-1,None) or b'Lua failure').decode(errors='replace'))
    finally:lua.lua_close(state)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('files',nargs='*',type=Path);a=p.parse_args()
    lua_root=ROOT/'addon/lan_dota/game/scripts/vscripts'
    for f in sorted(lua_root.rglob('*.lua')):run_lua(f.read_text(),str(f),False)
    files=a.files or sorted((ROOT/'tests/lua').glob('*_spec.lua'))
    prefix='package.path = '+repr(str(lua_root/'?.lua')+';'+str(lua_root/'?/init.lua')+';')+' .. package.path\n'
    for f in files:
        run_lua(prefix+f.read_text(),str(f));print('PASS '+str(f.relative_to(ROOT) if f.is_relative_to(ROOT) else f),flush=True)
    print('Lua 5.4 source syntax and mock fixtures only; Dota engine NOT run.',flush=True)
if __name__=='__main__':main()
