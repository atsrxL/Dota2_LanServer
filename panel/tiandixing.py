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
            # Original GetBotNames generates only five names, so extra bots get engine defaults.
            begin = text.find('function X.GetRandomNameList( sStarList )')
            if begin >= 0:
                end = text.index('function Think()', begin)
                names = text[begin:end]
                names = names.replace('function X.GetRandomNameList( sStarList )',
                    'function X.GetRandomNameList( sStarList )\n local copy = {}\n for i,name in ipairs(sStarList) do copy[i]=name end\n sStarList=copy')
                names = names.replace('for i = 1, 4', 'for i = 1, math.min(11, #sStarList)')
                text = text[:begin] + names + text[end:]

            for table in ('sSelectList', 'tSelectPoolList', 'tRecommendSelectPoolList'):
                text = text.replace(table+'[i]', table+'[((i - 1) % 5) + 1]')
            text = text.replace('return tLaneAssignList', '''-- LAN: native bots beyond slot five also need a valid assigned lane.
    for i = 6, #GetTeamPlayers(GetTeam()) do
        tLaneAssignList[i] = tLaneAssignList[((i - 1) % 5) + 1]
    end
    return tLaneAssignList''')
        if path.relative_to(root).as_posix() == 'FunLib/aba_item.lua':
            # The original assigned five outfit roles, then forced every extra slot to carry.
            text = text.replace('for i = 1, 5\n\tdo\n\t\tlocal memberID = nTeamPlayerIDs[i]',
                                'for i = 1, #nTeamPlayerIDs\n\tdo\n\t\tlocal memberID = nTeamPlayerIDs[i]')
            text = text.replace('return sOutfitTypeList[i]', 'return sOutfitTypeList[((i - 1) % 5) + 1]')
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
