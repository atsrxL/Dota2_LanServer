"""Version-scoped multiplayer fixes applied only to the transactional deployment copy."""
import re
from .bot_audit import mask_lua
from pathlib import Path

ITEM = '1573671599'
VERSION = 'ea5bacf5e672376dc1514f0758e7def17c48b28b8bf4a35a83c1308795f7f438'

def adapt(root: Path, spec: dict):
    if spec.get('item_id') != ITEM or spec.get('version') != VERSION:
        return
    available = {p.stem.removeprefix('hero_') for p in (root / 'BotLib').glob('hero_*.lua')}
    preferred = ['axe','bane','bloodseeker','crystal_maiden','drow_ranger','earthshaker','juggernaut','mirana','nevermore','phantom_lancer','puck','pudge','razor','sand_king','storm_spirit','sven','tiny','vengefulspirit','windrunner','zuus','kunkka','lina','lich','lion']
    spec['hero_pool'] = [name for name in preferred if name in available] + sorted(available - set(preferred))
    edits = {}
    for path in sorted(root.rglob('*.lua')):
        source = path.read_text(encoding='utf-8-sig')
        text = source
        # Only fixed loops that actually enumerate team members, not spell/item slots.
        text = re.sub(r'for (\w+) = 1, 5(\s+do\s+local \w+ = GetTeamMember\(\s*\1\s*\))',
                      r'for \1 = 1, #GetTeamPlayers( GetTeam() )\2', text)
        if path.name == 'hero_selection.lua':
            for table in ('sSelectList', 'tSelectPoolList', 'tRecommendSelectPoolList'):
                text = text.replace(table+'[i]', table+'[((i - 1) % 5) + 1]')
            text = text.replace('return tLaneAssignList', '''-- LAN: native bots beyond slot five also need a valid assigned lane.
    for i = 6, #GetTeamPlayers(GetTeam()) do
        tLaneAssignList[i] = tLaneAssignList[((i - 1) % 5) + 1]
    end
    return tLaneAssignList''')
        # Transient spawn invulnerability must not permanently abort entry loading.
        # Retain per-frame checks and exclusions for illusions/nonheroes.
        if path.parent == root and path.name != 'hero_selection.lua':
            boundary = re.search(r'\bfunction\b', mask_lua(text))
            end = boundary.start() if boundary else len(text)
            text = re.sub(r'if (?:bot|GetBot\(\)):IsInvulnerable\(\)\s+or ', 'if ', text[:end], count=1) + text[end:]
        if text != source:
            path.write_text(text, encoding='utf-8')
            edits[path.relative_to(root).as_posix()] = True
    spec['lan_team_extension'] = {'version': 1, 'files': sorted(edits)}
