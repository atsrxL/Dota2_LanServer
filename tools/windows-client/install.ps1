param([Parameter(Mandatory=$true)][string]$SteamRoot,
      [Parameter(Mandatory=$true)][string]$Payload,
      [string]$ResultFile)
$ErrorActionPreference = 'Stop'
$AddonDir = 'game\dota_addons\lan_dota'

# NSIS reads console output in the ANSI code page, so the message also goes to a UTF-16 file.
function Report([string]$Message) {
    Write-Output $Message
    if ($ResultFile) { [IO.File]::WriteAllText($ResultFile, $Message, (New-Object Text.UnicodeEncoding($false, $false))) }
}

# Registry SteamPath is lowercase with forward slashes; libraryfolders.vdf is not.
function Normalize([string]$Path) {
    return [IO.Path]::GetFullPath($Path.Replace('/', '\')).TrimEnd('\')
}

try {
    if (Get-Process dota2 -ErrorAction SilentlyContinue) { throw '请先退出 Dota 2，再重新安装。' }
    $SteamRoot = Normalize $SteamRoot
    $roots = @($SteamRoot)
    $vdf = Join-Path $SteamRoot 'steamapps\libraryfolders.vdf'
    if (Test-Path -LiteralPath $vdf) {
        $raw = Get-Content -LiteralPath $vdf -Raw
        foreach ($m in [regex]::Matches($raw, '"path"\s*"([^"]+)"')) {
            $roots += $m.Groups[1].Value.Replace('\\', '\')
        }
    }
    $candidates = @($SteamRoot)
    foreach ($r in $roots) { $candidates += Join-Path $r 'steamapps\common\dota 2 beta' }
    $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $games = @()
    foreach ($c in $candidates) {
        $n = Normalize $c
        if ($seen.Add($n) -and (Test-Path -LiteralPath (Join-Path $n 'game\bin\win64\dota2.exe'))) { $games += $n }
    }
    if ($games.Count -eq 0) { throw '未找到 Dota 2。请选择 Steam 安装目录、Steam 库目录或 dota 2 beta 目录。' }
    if ($games.Count -gt 1) { throw ('发现多个 Dota 2 安装，请直接选择需要更新的 dota 2 beta 目录：' + ($games -join '；')) }
    $game = $games[0]
    $manifest = @(Get-Content -LiteralPath (Join-Path $Payload 'files.json') -Raw | ConvertFrom-Json)
    $wanted = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($f in $manifest) {
        if ($f.path -notlike 'game/dota_addons/lan_dota/*' -or $f.path.Contains('..') -or $f.path.Contains(':')) { throw '资源路径无效。' }
        [void]$wanted.Add($f.path.Replace('/', '\'))
    }
    # Files left over from an older release of this addon; the directory is owned by this installer.
    $stale = @()
    $addonRoot = Join-Path $game $AddonDir
    if (Test-Path -LiteralPath $addonRoot) {
        foreach ($item in Get-ChildItem -LiteralPath $addonRoot -Recurse -File -Force) {
            $rel = $item.FullName.Substring($game.Length + 1)
            if (-not $wanted.Contains($rel)) { $stale += $rel }
        }
    }
    $backup = Join-Path $env:LOCALAPPDATA ('Dota2LAN\Backups\' + [guid]::NewGuid().ToString())
    $targets = @($manifest | ForEach-Object { $_.path.Replace('/', '\') }) + $stale
    foreach ($rel in $targets) {
        $dst = Join-Path $game $rel
        $parent = $dst
        while ($parent -and $parent.Length -ge $game.Length) {
            if ((Test-Path -LiteralPath $parent) -and ((Get-Item -LiteralPath $parent -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw '目标包含目录链接，请使用普通游戏目录安装。' }
            $parent = Split-Path $parent -Parent
        }
        if (Test-Path -LiteralPath $dst) {
            $old = Join-Path $backup $rel
            New-Item -ItemType Directory -Path (Split-Path $old) -Force | Out-Null
            Copy-Item -LiteralPath $dst -Destination $old
        }
    }
    foreach ($f in $manifest) {
        $src = Join-Path $Payload $f.path.Replace('/', '\')
        if ((Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash -ne $f.sha256) { throw '安装包资源校验失败，请重新下载。' }
    }
    $written = @()
    try {
        foreach ($f in $manifest) {
            $rel = $f.path.Replace('/', '\')
            $dst = Join-Path $game $rel
            New-Item -ItemType Directory -Path (Split-Path $dst) -Force | Out-Null
            $written += $rel
            Copy-Item -LiteralPath (Join-Path $Payload $rel) -Destination $dst -Force
            if ((Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash -ne $f.sha256) { throw '写入校验失败。' }
        }
        foreach ($rel in $stale) {
            $written += $rel
            Remove-Item -LiteralPath (Join-Path $game $rel) -Force
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
    $lines = @("安装完成：$game", "已覆盖 $($manifest.Count) 个客户端资源文件。")
    if ($stale.Count) { $lines += "已移除 $($stale.Count) 个旧版残留文件。" }
    if (Test-Path -LiteralPath $backup) { $lines += "原文件备份：$backup" }
    Report ($lines -join "`r`n")
    exit 0
} catch {
    Report $_.Exception.Message
    exit 1
}
