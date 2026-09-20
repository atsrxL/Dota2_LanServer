Unicode true
!include "MUI2.nsh"
Name "Dota 2 LAN 客户端资源"
OutFile "Dota2-LAN-Client.exe"
RequestExecutionLevel admin
SetCompressor /SOLID lzma
InstallDir "$PROGRAMFILES32\Steam"
!define MUI_DIRECTORYPAGE_TEXT_TOP "请选择 Steam 安装目录。安装器会查找其他 Steam 库中的 Dota 2。也可直接选择 dota 2 beta 目录。请先退出 Dota 2。"
!define MUI_DIRECTORYPAGE_TEXT_DESTINATION "Steam / Dota 2 目录"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"
Function .onInit
  ReadRegStr $0 HKCU "Software\Valve\Steam" "SteamPath"
  StrCmp $0 "" +2
  StrCpy $INSTDIR $0
FunctionEnd
Section
  InitPluginsDir
  SetOutPath "$PLUGINSDIR\payload"
  File /r "payload/*"
  SetOutPath "$PLUGINSDIR"
  File "install.ps1"
  nsExec::ExecToStack '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\install.ps1" -SteamRoot "$INSTDIR" -Payload "$PLUGINSDIR\payload"'
  Pop $0
  Pop $1
  DetailPrint "$1"
  StrCmp $0 "0" success
  MessageBox MB_OK|MB_ICONSTOP "安装未完成：$\r$\n$1"
  SetErrorLevel 1
  Abort
success:
  MessageBox MB_OK|MB_ICONINFORMATION "$1"
SectionEnd
