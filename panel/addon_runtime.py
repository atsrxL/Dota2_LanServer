"""Bounded per-process telemetry. Console output is evidence, not attestation."""
from __future__ import annotations
import json
import re
import threading
import time
from collections import deque

class AddonTelemetry:
    def __init__(self, session: str, clock=time.monotonic):
        self.session = session; self.clock = clock; self.lock = threading.RLock()
        self.buffer = ''; self.state = None; self.seen = None; self.started = clock()
        self.events = deque(maxlen=100); self.entries = set(); self.callbacks = {}; self.api_missing = {}
        self.contexts = {}; self.errors = deque(maxlen=20); self.rejections = set(); self.dropped = 0

    def feed(self, chunk: str):
        with self.lock:
            self.buffer += chunk
            lines = self.buffer.split('\n'); self.buffer = lines.pop()[-16384:]
            for line in lines:
                line = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', line).strip('\r')
                for prefix in ('[VScript] ', '[Server] '):
                    if line.startswith(prefix): line=line[len(prefix):]
                if len(line) > 16384: self.dropped += 1; continue
                if '#GameUI_ServerNoLobby' in line: self.rejections.add('ServerNoLobby')
                if 'S2C_CONNREJECT' in line: self.rejections.add('connection_rejected_check_log')
                if not line.startswith('LANLAB|' + self.session + '|'): continue
                try: _, _, kind, detail = line.split('|', 3)
                except ValueError: continue
                if kind == 'STATE':
                    try:
                        obj = json.loads(detail)
                        if (not isinstance(obj, dict) or obj.get('phase') not in
                            {'waiting_engine','setup','starting','hero_selection','pregame','playing','postgame','error'}
                            or not isinstance(obj.get('players'), list) or len(obj['players']) > 64): continue
                        self.state = obj; self.seen = self.clock()
                    except (ValueError, RecursionError): continue
                elif kind in {'BOOT','ERROR','CAPS','BOT_ENTRY','BOT_CALLBACK','BOT_API','BOT_CONTEXT','UI_HELLO','START','FILL'}:
                    self.events.append({'elapsed': round(self.clock()-self.started, 1), 'kind': kind, 'detail': detail[:1500]})
                    if kind == 'ERROR': self.errors.append(detail[:1000])
                    if kind == 'BOT_ENTRY' and len(self.entries)<500: self.entries.add(detail.split(':',1)[0][:200])
                    elif kind == 'BOT_CALLBACK':
                        parts = detail.split(':')
                        if len(parts) == 3 and len(parts[2])<=18 and parts[2].isdigit():
                            key = ':'.join(parts[:2])[:256]
                            if len(self.callbacks)<500 or key in self.callbacks: self.callbacks[key] = max(self.callbacks.get(key,0),int(parts[2]))
                    elif kind == 'BOT_API':
                        file, _, missing = detail.partition(':')
                        if len(self.api_missing)<500: self.api_missing[file[:200]] = [] if missing == 'present' else [x[:128] for x in missing.split(',')[:100]]
                    elif kind == 'BOT_CONTEXT':
                        file, _, context = detail.partition(':')
                        if len(self.contexts)<500: self.contexts[file[:200]] = context[:200]

    def snapshot(self, running: bool) -> dict:
        with self.lock:
            age = None if self.seen is None else max(0,self.clock()-self.seen)
            return {'session': self.session, 'running': running, 'fresh': bool(running and age is not None and age < 15),
                    'heartbeat_age_seconds': None if age is None else round(age,1), 'state': self.state,
                    'events': list(self.events), 'bot_entries': sorted(self.entries), 'bot_callbacks': dict(self.callbacks),
                    'bot_missing_apis': dict(self.api_missing), 'bot_contexts': dict(self.contexts),
                    'errors': list(self.errors), 'connection_rejections': sorted(self.rejections),
                    'dropped_lines': self.dropped, 'full_ai_verified': False,
                    'notice': '日志为当前进程证据，不是防伪认证。未检测到不等于不存在；行为与整场对局仍需人工验收。'}
