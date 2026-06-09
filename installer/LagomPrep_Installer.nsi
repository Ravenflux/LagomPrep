; LagomPrep Windows Installer Script
; Build with: makensis LagomPrep_Installer.nsi
; Requires NSIS installed from https://nsis.sourceforge.io

;--------------------------------
; General

!define APP_NAME "LagomPrep"
!define APP_VERSION "1.0"
!define APP_PUBLISHER "LagomPrep"
!define APP_URL "https://github.com"
!define APP_EXE "LagomPrep.exe"
!define INSTALL_DIR "$PROGRAMFILES64\LagomPrep"

Name "${APP_NAME} ${APP_VERSION}"
OutFile "LagomPrep_Setup.exe"
InstallDir "${INSTALL_DIR}"
InstallDirRegKey HKLM "Software\LagomPrep" "Install_Dir"
RequestExecutionLevel admin
BrandingText "Lagom is a Swedish word meaning 'just enough'"

;--------------------------------
; Interface

!include "MUI2.nsh"

!define MUI_ABORTWARNING
!define MUI_ICON "..\static\icon.ico"
!define MUI_UNICON "..\static\icon.ico"
!define MUI_WELCOMEPAGE_TITLE "Welcome to LagomPrep"
!define MUI_WELCOMEPAGE_TEXT "LagomPrep is a meal planning and recipe manager.$\r$\n$\r$\nThis will install LagomPrep ${APP_VERSION} on your computer.$\r$\n$\r$\nClick Next to continue."
!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "Launch LagomPrep now"
!define MUI_FINISHPAGE_SHOWREADME "$INSTDIR\README.txt"
!define MUI_FINISHPAGE_SHOWREADME_TEXT "View README"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

;--------------------------------
; Installer

Section "LagomPrep (required)" SecMain
  SectionIn RO
  SetOutPath "$INSTDIR"

  ; Main executable
  File "..\dist\LagomPrep.exe"

  ; README
  File "..\README.txt"

  ; LICENSE.txt
  File "..\LICENSE.txt"

  ; Write install location to registry
  WriteRegStr HKLM "Software\LagomPrep" "Install_Dir" "$INSTDIR"

  ; Write uninstaller registry keys
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\LagomPrep" \
    "DisplayName" "LagomPrep"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\LagomPrep" \
    "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\LagomPrep" \
    "Publisher" "${APP_PUBLISHER}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\LagomPrep" \
    "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\LagomPrep" \
    "DisplayIcon" "$INSTDIR\${APP_EXE}"
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\LagomPrep" \
    "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\LagomPrep" \
    "NoRepair" 1

  ; Create uninstaller
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; Start Menu shortcuts
  CreateDirectory "$SMPROGRAMS\LagomPrep"
  CreateShortcut "$SMPROGRAMS\LagomPrep\LagomPrep.lnk" "$INSTDIR\${APP_EXE}"
  CreateShortcut "$SMPROGRAMS\LagomPrep\Uninstall LagomPrep.lnk" "$INSTDIR\Uninstall.exe"

SectionEnd

;--------------------------------
; Optional desktop shortcut

Section "Desktop Shortcut" SecDesktop
  CreateShortcut "$DESKTOP\LagomPrep.lnk" "$INSTDIR\${APP_EXE}"
SectionEnd

;--------------------------------
; Section descriptions

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecMain} "Installs LagomPrep and creates Start Menu shortcuts."
  !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} "Creates a shortcut on your Desktop."
!insertmacro MUI_FUNCTION_DESCRIPTION_END

;--------------------------------
; Uninstaller

Section "Uninstall"

  ; Ask user if they want to keep their data
  MessageBox MB_YESNO|MB_ICONQUESTION \
    "Do you want to keep your recipe data?$\r$\n$\r$\nClick YES to keep your recipes, meal plans, and settings.$\r$\nClick NO to completely remove all LagomPrep data." \
    IDYES keep_data

  ; Full removal — delete database too
  Delete "$INSTDIR\lagomprep.db"
  Delete "$INSTDIR\recipevault.db"
  RMDir /r "$INSTDIR"
  Goto done_data

  keep_data:
  ; Partial removal — keep database
  Delete "$INSTDIR\LagomPrep.exe"
  Delete "$INSTDIR\README.txt"
  Delete "$INSTDIR\LICENSE.txt"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"

  done_data:
  ; Remove shortcuts either way
  Delete "$SMPROGRAMS\LagomPrep\LagomPrep.lnk"
  Delete "$SMPROGRAMS\LagomPrep\Uninstall LagomPrep.lnk"
  RMDir "$SMPROGRAMS\LagomPrep"
  Delete "$DESKTOP\LagomPrep.lnk"

  ; Remove registry keys either way
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\LagomPrep"
  DeleteRegKey HKLM "Software\LagomPrep"

  ; Remove temp files PyInstaller may have left
  RMDir /r "$TEMP\_MEI*"

SectionEnd