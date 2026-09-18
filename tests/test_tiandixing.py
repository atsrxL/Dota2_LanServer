from panel.tiandixing import adapt, ITEM, VERSION


def test_deployment_extension_preserves_frame_guards_and_original_five(tmp_path):
    root=tmp_path/'deployment';root.mkdir()
    source='''if bot:IsInvulnerable() or not bot:IsHero() then return end
function Think()
 if bot:IsInvulnerable() or bot:IsIllusion() then return end
 for i = 1, 5 do local ally = GetTeamMember( i ) end
 for i = 1, 5 do local item = bot:GetItemInSlot(i) end
end'''
    (root/'mode_laning_generic.lua').write_text(source)
    (root/'hero_selection.lua').write_text('''function UpdateLaneAssignments()
 return tLaneAssignList
end
function Think() local chosen=sSelectList[i] end''')
    (root/'BotLib').mkdir()
    (root/'BotLib/hero_axe.lua').write_text('return {}')
    (root/'BotLib/hero_luna.lua').write_text('return {}')
    spec={'item_id':ITEM,'version':VERSION};adapt(root,spec)
    assert spec['hero_pool']==['axe','luna']
    text=(root/'mode_laning_generic.lua').read_text()
    assert text.startswith('if not bot:IsHero()')
    assert 'if bot:IsInvulnerable() or bot:IsIllusion()' in text
    assert '1, #GetTeamPlayers( GetTeam() )' in text
    assert '1, 5 do local item' in text
    assert 'for i = 6, #GetTeamPlayers(GetTeam())' in (root/'hero_selection.lua').read_text()
    assert len(spec['lan_team_extension']['files'])==2


def test_other_versions_unchanged(tmp_path):
    p=tmp_path/'hero_selection.lua';p.write_text('return tLaneAssignList')
    adapt(tmp_path,{'item_id':ITEM,'version':'different'})
    assert p.read_text()=='return tLaneAssignList'


def test_outfit_roles_extend_beyond_five(tmp_path):
    (tmp_path/'FunLib').mkdir()
    p=tmp_path/'FunLib/aba_item.lua'
    p.write_text('for i = 1, 5\n\tdo\n\t\tlocal memberID = nTeamPlayerIDs[i]\nreturn sOutfitTypeList[i]\nend')
    adapt(tmp_path,{'item_id':ITEM,'version':VERSION})
    text=p.read_text()
    assert 'for i = 1, #nTeamPlayerIDs' in text
    assert 'sOutfitTypeList[((i - 1) % 5) + 1]' in text


def test_bot_names_cover_twelve_without_consuming_source(tmp_path):
    p=tmp_path/'hero_selection.lua'
    p.write_text("function X.GetRandomNameList( sStarList )\nlocal sNameList={sStarList[1]}\ntable.remove(sStarList,1)\nfor i = 1, 4 do table.insert(sNameList,table.remove(sStarList,1)) end\nreturn sNameList\nend\nfunction Think() end")
    adapt(tmp_path,{'item_id':ITEM,'version':VERSION})
    text=p.read_text()
    assert 'math.min(11, #sStarList)' in text
    assert 'sStarList=copy' in text
