param([Parameter(Mandatory=$true)][string]$SteamRoot,
      [Parameter(Mandatory=$true)][string]$Payload)
$ErrorActionPreference = 'Stop'
try {
    if (Get-Process dota2 -ErrorAction SilentlyContinue) { throw '请先退出 Dota 2，再重新安装。' }
    $SteamRoot = [IO.Path]::GetFullPath($SteamRoot)
    $roots = @($SteamRoot)
    $vdf = Join-Path $SteamRoot 'steamapps/libraryfolders.vdf'
    if (Test-Path -LiteralPath $vdf) {
        $raw = Get-Content -LiteralPath $vdf -Raw
        foreach ($m in [regex]::Matches($raw, '"path"\s*"([^"]+)"')) {
            $roots += $m.Groups[1].Value.Replace('\\', '\')
        }
    }
    $candidates = @($SteamRoot)
    foreach ($r in $roots) { $candidates += Join-Path $r 'steamapps/common/dota 2 beta' }
    $games = @($candidates | Select-Object -Unique | Where-Object {
        Test-Path -LiteralPath (Join-Path $_ 'game/bin/win64/dota2.exe')
    })
    if ($games.Count -eq 0) { throw '未找到 Dota 2。请选择 Steam 安装目录、Steam 库目录或 dota 2 beta 目录。' }
    if ($games.Count -gt 1) { throw '发现多个 Dota 2 安装，请直接选择需要更新的 dota 2 beta 目录。' }
    $game = $games[0]
    $manifest = Get-Content -LiteralPath (Join-Path $Payload 'files.json') -Raw | ConvertFrom-Json
    $backup = Join-Path $env:LOCALAPPDATA ('Dota2LAN/Backups/' + [guid]::NewGuid().ToString())
    $written = @()
    foreach ($f in $manifest) {
        if ($f.path -notlike 'game/dota_addons/lan_dota/*' -or $f.path.Contains('..') -or $f.path.Contains(':')) { throw '资源路径无效。' }
        $src = Join-Path $Payload $f.path
        if ((Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash -ne $f.sha256) { throw '安装包资源校验失败，请重新下载。' }
        $dst = Join-Path $game $f.path
        $parent = $dst
        while ($parent -and $parent.Length -ge $game.Length) {
            if ((Test-Path -LiteralPath $parent) -and ((Get-Item -LiteralPath $parent).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw '目标包含目录链接，请使用普通游戏目录安装。' }
            $parent = Split-Path $parent -Parent
        }
        if (Test-Path -LiteralPath $dst) {
            $old = Join-Path $backup $f.path
            New-Item -ItemType Directory -Path (Split-Path $old) -Force | Out-Null
            Copy-Item -LiteralPath $dst -Destination $old
        }
    }
    try {
        foreach ($f in $manifest) {
            $dst = Join-Path $game $f.path
            New-Item -ItemType Directory -Path (Split-Path $dst) -Force | Out-Null
            $written += $f.path
            Copy-Item -LiteralPath (Join-Path $Payload $f.path) -Destination $dst -Force
            if ((Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash -ne $f.sha256) { throw '写入校验失败。' }
        }
    } catch {
        foreach ($rel in $written) {
            $old = Join-Path $backup $rel
            $dst = Join-Path $game $rel
            if (Test-Path -LiteralPath $old) { Copy-Item -LiteralPath $old -Destination $dst -Force }
            else { Remove-Item -LiteralPath $dst -Force -ErrorAction SilentlyContinue }
        }
        throw
    }
    Write-Output "安装完成：$game"
    Write-Output "已覆盖 $($manifest.Count) 个客户端资源文件。"
    if (Test-Path -LiteralPath $backup) { Write-Output "原文件备份：$backup" }
    exit 0
} catch {
    Write-Output $_.Exception.Message
    exit 1
}
