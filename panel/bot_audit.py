"""Non-executing Lua audit and reversible, deployment-only native Bot probes.

The lexer masks comments and strings while preserving character offsets. It is
not a Lua parser or a proof of compatibility. No API is emulated and no bot file
is imported into the addon's server VM. Runtime probes execute in the VM the
Dota engine actually chooses for the original Bot entry.
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from .bot_files import inventory
from .common import Fault, now

BOT_GLOBALS = frozenset('''GetBot GetScriptDirectory GetTeam GetTeamPlayers GetTeamMember GetTeamForPlayer
IsPlayerBot IsHeroAlive GetSelectedHeroName SelectHero GetGameState DotaTime GameTime RealTime
GetUnitList GetLaneFrontLocation GetLaneFrontAmount GetLaneFrontDesire GetLaneFrontDesire
GetPushLaneDesire GetDefendLaneDesire GetRoamDesire GetRoshanDesire GetFarmLaneDesire
GetAmountAlongLane GetTower GetBarracks GetAncient GetShopLocation GetRuneStatus GetRuneSpawnLocation
GetItemCost GetItemStockCount GetItemComponents GetHeroLevel GetTeamKills GetTeamDeaths
GetOpposingTeam GetHeroLastSeenInfo GetUnitToUnitDistance GetUnitToLocationDistance
GetBotNames GetNumHumanPlayers GetNumBots GetMatchID GetDifficulty GetCourier GetNumCouriers
GetNeutralSpawners GetAvoidanceZones GetIncomingTeleports GetTreeLocation GetWorldBounds
GetHeightLevel GetHeroPickState GetHeroPickStateTimeRemaining GetHeroPickStateTimeElapsed
GetPlayerTeam IsLocationPassable RandomInt RandomFloat RandomVector GetTeamItem
'''.split())
CALLBACKS = ('Think', 'AbilityUsageThink', 'ItemUsageThink', 'ItemPurchaseThink',
             'MinionThink', 'GetDesire', 'CourierUsageThink', 'BuybackUsageThink', 'AbilityLevelUpThink')
LONG_OPEN = re.compile(r'\[(=*)\[')
ENTRY = re.compile(r'^(?:hero_selection|bot_generic|bot_[a-z0-9_]+|ability_item_usage_[a-z0-9_]+|item_purchase_[a-z0-9_]+|mode_[a-z0-9_]+|minion_[a-z0-9_]+)\.lua$')


def mask_lua(text: str, keep_strings: bool = False) -> str:
    """Mask Lua 5.x quoted/long strings and comments without changing offsets."""
    chars = list(text); n = len(text); i = 0
    def erase(a, b):
        for k in range(a, b):
            if chars[k] not in '\r\n': chars[k] = ' '
    while i < n:
        begin = i; comment = text.startswith('--', i)
        pos = i + 2 if comment else i
        long = LONG_OPEN.match(text, pos)
        if long:
            endmark = ']' + long[1] + ']'
            end = text.find(endmark, pos + len(long[0]))
            end = n if end < 0 else end + len(endmark)
            if comment or not keep_strings: erase(begin, end)
            i = end
        elif comment:
            end = text.find('\n', i); end = n if end < 0 else end
            erase(i, end); i = end
        elif text[i] in "\"'":
            quote = text[i]; i += 1
            while i < n:
                if text[i] == '\\': i += 2; continue
                if text[i] == quote: i += 1; break
                i += 1
            i = min(n, i)
            if not keep_strings: erase(begin, i)
        else: i += 1
    return ''.join(chars)


def audit_scripts(root: Path, selection: dict) -> dict:
    sha, files, total = inventory(root)
    if sha != selection.get('version'):
        raise Fault('审计前版本校验失败；不读取已被修改的脚本', 409)
    results = []; globals_found = set(); callbacks = set(); unresolved = []; dependencies = []
    for file in sorted(root.rglob('*.lua')):
        if file.is_symlink() or file.stat().st_size > 4 * 1024 * 1024:
            raise Fault('Lua 审计拒绝链接或超过 4 MiB 的单文件', 409)
        relative = file.relative_to(root).as_posix()
        try: text = file.read_text(encoding='utf-8-sig')
        except UnicodeError:
            unresolved.append({'file': relative, 'reason': 'not_utf8'}); continue
        masked = mask_lua(text)
        # Exclude members (foo.GetBot / foo:GetBot). This is a candidate list,
        # not scope resolution: locally defined names are still reported.
        calls = set(re.findall(r'(?<![\w.:])([A-Za-z_][A-Za-z_0-9]*)\s*\(', masked))
        required = sorted(calls & BOT_GLOBALS); globals_found.update(required)
        defined = [x for x in CALLBACKS if re.search(r'\bfunction\s+' + x + r'\s*\(', masked)]
        callbacks.update(defined)
        literals = mask_lua(text, keep_strings=True)
        loads = list(re.finditer(r'\b(require|dofile)\s*\(?\s*([\"\'])([^\"\'\n]+)\2', literals))
        for match in loads:
            value = match[3]
            dependencies.append({'file': relative, 'loader': match[1], 'literal': value[:200]})
        if len(re.findall(r'\b(?:require|dofile)\s*\(', masked)) > len(loads):
            unresolved.append({'file': relative, 'reason': 'dynamic_module_path'})
        results.append({'file': relative, 'bot_globals': required, 'callbacks': defined,
                        'probe_candidate': bool(ENTRY.fullmatch(file.name) and file.parent == root)})
    return {'schema': 1, 'created_at': now(), 'selection': selection, 'content_sha256': sha,
            'files': len(files), 'bytes': total, 'lua_files': len(results),
            'bot_globals': sorted(globals_found), 'callbacks': sorted(callbacks),
            'entries': [x['file'] for x in results if x['probe_candidate']],
            'dependencies': dependencies[:300], 'unresolved': unresolved[:300],
            'details': results[:500], 'truncated': len(results)>500 or len(dependencies)>300 or len(unresolved)>300,
            'static_result': 'inventory_only_runtime_required', 'runtime_verified': False,
            'notice': '只扫描文本；动态 require、对象方法、局部遮蔽及引擎行为未被证明。未执行第三方 Lua。'}


def probe_header(session: str, entry: str, globals_used: list[str]) -> str:
    if not re.fullmatch(r'[a-f0-9]{32}', session): raise Fault('实验会话 ID 无效')
    if not re.fullmatch(r'[a-zA-Z0-9_]+\.lua', entry): raise Fault('探针入口名无效')
    api = ','.join(json.dumps(x) for x in sorted(set(globals_used) | {'GetBot','GetScriptDirectory'}) if x in BOT_GLOBALS)
    # All probe work is pcall-guarded. AI callback errors are NOT caught here;
    # they remain visible to the engine. No replacement GetBot or fake result.
    return '''-- LANLAB deployment probe: original library content remains untouched.
local __lanlab_probe_130 = (function()
    local counts = {}
    local prefix = "LANLAB|%s|"
    local entry = %s
    local function emit(kind, detail)
        print(prefix .. kind .. "|" .. entry .. ":" .. tostring(detail))
    end
    pcall(function()
        emit("BOT_ENTRY", "loaded")
        local missing = {}; local names = {%s}
        for _, name in ipairs(names) do
            if type(_G[name]) ~= "function" then table.insert(missing, name) end
        end
        emit("BOT_API", #missing == 0 and "present" or table.concat(missing, ","))
        if type(GetBot) == "function" then
            local ok, bot = pcall(GetBot)
            emit("BOT_CONTEXT", ok and bot ~= nil and "bot_handle" or "no_handle")
        else emit("BOT_CONTEXT", "GetBot_missing") end
    end)
    return function(callback)
        pcall(function()
            counts[callback] = (counts[callback] or 0) + 1
            local n = counts[callback]
            if n == 1 or n == 64 or n == 1024 or n %% 8192 == 0 then
                emit("BOT_CALLBACK", callback .. ":" .. tostring(n))
                local bot = type(GetBot)=="function" and GetBot() or nil
                if bot then emit("BOT_ACTOR", tostring(bot:GetPlayerID()) .. ":" .. bot:GetUnitName() .. ":" .. callback .. ":" .. tostring(n)) end
            end
        end)
    end
end)()
''' % (session, json.dumps(entry), api)


def instrument_scripts(root: Path, spec: dict, session: str, report: dict) -> dict:
    """Called inside BotLibrary's transaction BEFORE deployment hash is saved."""
    entries = []; injected = 0
    for file in sorted(root.glob('*.lua')):
        if not ENTRY.fullmatch(file.name): continue
        text = file.read_text(encoding='utf-8-sig')
        masked = mask_lua(text)
        pattern = r'\bfunction\s+(' + '|'.join(CALLBACKS) + r')\s*\([^()]*\)'
        edits = [(m.end(), '\n__lanlab_probe_130(' + json.dumps(m[1]) + ')\n') for m in re.finditer(pattern, masked)]
        # Inserting inside declared callback bodies does not move the original
        # code, wrap its return values or append illegal code after top-level return.
        for pos, insert in reversed(edits): text = text[:pos] + insert + text[pos:]
        text = probe_header(session, file.name, report['bot_globals']) + text
        file.write_text(text, encoding='utf-8')
        entries.append(file.name); injected += len(edits)
    if not entries: raise Fault('未找到可探测的原生 Bot 入口；保留库文件，不猜测入口', 409)
    spec['lan_probe'] = {'session': session, 'entries': entries, 'callbacks_instrumented': injected}
    return spec['lan_probe']
