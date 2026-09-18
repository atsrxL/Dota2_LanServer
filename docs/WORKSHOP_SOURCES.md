# Workshop 实现依据与验证边界

核查日期：2026-09-16。公开协议/文档是实现参考，不是本项目在真实 Dota/PVE 已运行的证据。

1. Valve Steamworks ISteamRemoteStorage，GetPublishedFileDetails：固定 POST 与参数，查询条目资料。本版不抓取网页 HTML、不需要用户提供 Steam Web API key。
   https://partner.steamgames.com/doc/webapi/ISteamRemoteStorage
2. Valve Steamworks Workshop / ISteamUGC：下载与已安装内容是不同状态，需检查成功/安装目录。
   https://partner.steamgames.com/doc/api/ISteamUGC
   https://partner.steamgames.com/doc/features/workshop/implementation
3. 目标作者 Workshop 页面，1627071163：“天地星AI · 固定搭配”，机器人脚本条目；名称和作者说明以当前页面为准。
   https://steamcommunity.com/sharedfiles/filedetails/?id=1627071163
4. Valve Developer Community，Dota Bot Scripting：服务端 Lua 与本地开发脚本目录说明。它不构成当前 Linux -dedicated 整体方案的兼容性证明。
   https://developer.valvesoftware.com/wiki/Dota_Bot_Scripting
5. Valve Developer Community，VPK file format：标准 v1/v2 头、目录树、预载、嵌入/外部分卷及 CRC。解析器另外做了边界/路径限制。真实目标包格式尚未获取验证。
   https://developer.valvesoftware.com/wiki/VPK_(file_format)
6. 公开提取的 Dota 房间协议包含 bot_radiant / bot_dire / difficulty 等字段。这里只列为未来房间同步的研究依据；当前没有实现它们的读写。
   https://github.com/SteamTracking/GameTracking-Dota2/blob/master/Protobufs/dota_gcmessages_client_match_management.proto

本次没有真实下载 1627071163，没有获取其源码内容或对其 Lua 进行审计，也没有实测其 Linux Dedicated 行为。示例/测试源是自建最小 fixture，不包含或冒充作者脚本。不将本地内容 SHA 当作上游 manifest。SteamCMD 英文提示、控制变量和上游包格式变化都需要按真实输出补充测试。
