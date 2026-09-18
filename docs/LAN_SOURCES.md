# 1.3.0 接口依据与不确定项

核对日期：2026-09-18。只作为开发依据，未访问实际用户PVE或当前游戏二进制。部分Valve Wiki/GitHub细文件读取失败；没有用缺失结果假称已核对。

1. ModDota Server API：https://docs.moddota.com/lua_server/
   - EnableCustomGameSetupAutoLaunch、SetCustomGameSetupTimeout、FinishCustomGameSetup、LockCustomGameSetupTeamAssignment。
   - SetBotThinkingEnabled 的描述限定标准dota地图/default heroes。
   - GameRules:BotPopulate 描述注明需要cheat mode，因此源码显式检查，不自行开作弊。
   - CustomGameEventManager、CustomNetTables、PlayerResource方法的接口存在性，不等于当前Dota二进制行为已验收。
2. ModDota Bot API：https://docs.moddota.com/lua_bots/
   - 识别原生Bot函数与另一运行环境。源码只收集候选，不模拟这些API。
3. ModDota TypeScriptAddonTemplate：https://github.com/ModDota/TypeScriptAddonTemplate
   - game/content分离及Panorama/VScripts开发结构参考；本包未复制模板或引入TypeScript构建依赖。
4. Windy10v10AI 作者README：https://github.com/windy10v10ai/game
   - 给出Workshop Tools开发、game/content结构、`dota_launch_custom_game windy10v10ai dota` 的本地VConsole用法。
   - 不能据此宣称Linux dedicated启动参数已通过。未复制该项目GPL代码或AI。
5. ValveResourceFormat Resource.cs：https://github.com/ValveResourceFormat/ValveResourceFormat/blob/master/ValveResourceFormat/Resource/Resource.cs
   - Source2资源头v12、块表/偏移格式的检查依据。我们只写有界头/块校验，不复制其完整解析器、不生成伪编译文件。
6. 天地星Workshop目标：https://steamcommunity.com/sharedfiles/filedetails/?id=1627071163
   - 下载器在目标环境查真实元数据和文件；未将作者脚本重新分发。是否允许公开捆绑应另行确认。

7. Valve Custom Nettables：https://developer.valvesoftware.com/wiki/Dota_2_Workshop_Tools/Custom_Nettables
   - 搜索可见说明要求在scripts/custom_net_tables.txt注册顶层表；完整页面本环境403。交付使用KV3数组形式而非旧KV1字典。
   - KV3文本示例还与开发者实用示例交叉检查：https://customgames.ru/forum/threads/customnettables-не-может-задать-значение.815/ 。仅作格式线索，不替代引擎实测。

仍需本地核对：当前引擎的addoninfo/custom_net_tables格式、GameSetup/Hud实际装载、事件回调source是否为实体索引、两种Linux启动候选、原生Bot加载路径、天地星槽位和AI行为。mock里的常量/函数仅是测试边界，不作为上游行为证据。
