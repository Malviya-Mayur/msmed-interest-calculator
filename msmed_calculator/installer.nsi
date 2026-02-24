; =============================================================================
; MSMED Act Interest Calculator — NSIS Installer Script
;
; Produces: MSMED_Calculator_Setup.exe
; Requirements (on Windows build machine):
;   1. Python 3.11+ on PATH
;   2. NSIS installed → https://nsis.sourceforge.io/Download
;
; Build via:  build_windows.bat  (handles PyInstaller + makensis automatically)
;   OR manually:
;     pyinstaller msme_calculator.spec --clean --noconfirm
;     makensis installer.nsi
; =============================================================================

Unicode True

; ── Metadata ─────────────────────────────────────────────────────────────────
!define APP_NAME        "MSMED Interest Calculator"
!define APP_VERSION     "1.0.0"
!define APP_PUBLISHER   "Malviya-Mayur"
!define APP_EXE         "msme_calculator.exe"
!define INSTALL_DIR     "$PROGRAMFILES64\${APP_NAME}"
!define UNINSTALL_KEY   "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"

; ── General settings ─────────────────────────────────────────────────────────
Name            "${APP_NAME} ${APP_VERSION}"
OutFile         "MSMED_Calculator_Setup.exe"
InstallDir      "${INSTALL_DIR}"
InstallDirRegKey HKLM "${UNINSTALL_KEY}" "InstallLocation"
RequestExecutionLevel admin
SetCompressor   /SOLID lzma

; ── Pages ─────────────────────────────────────────────────────────────────────
!include "MUI2.nsh"

!define MUI_ABORTWARNING
!define MUI_ICON        "${NSISDIR}\Contrib\Graphics\Icons\modern-install.ico"
!define MUI_UNICON      "${NSISDIR}\Contrib\Graphics\Icons\modern-uninstall.ico"
!define MUI_WELCOMEPAGE_TITLE   "Welcome to ${APP_NAME} Setup"
!define MUI_WELCOMEPAGE_TEXT    "This wizard will install ${APP_NAME} ${APP_VERSION} on your computer.$\r$\n$\r$\nThe application calculates interest on delayed MSME vendor payments as required by Section 16 of the MSMED Act, 2006.$\r$\n$\r$\nClick Next to continue."
!define MUI_FINISHPAGE_RUN          "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT     "Launch ${APP_NAME} now"
!define MUI_FINISHPAGE_SHOWREADME   "$INSTDIR\README.md"
!define MUI_FINISHPAGE_SHOWREADME_TEXT "View README"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

; ── Install Section ────────────────────────────────────────────────────────────
Section "Install"
    SetOutPath "$INSTDIR"

    ; Copy application executable
    File "dist\${APP_EXE}"

    ; Copy README
    File "README.md"

    ; Copy sample data file
    File "Sample File.xlsx"

    ; Write uninstaller
    WriteUninstaller "$INSTDIR\Uninstall.exe"

    ; Register in Windows Programs and Features
    WriteRegStr HKLM "${UNINSTALL_KEY}" "DisplayName"      "${APP_NAME}"
    WriteRegStr HKLM "${UNINSTALL_KEY}" "DisplayVersion"   "${APP_VERSION}"
    WriteRegStr HKLM "${UNINSTALL_KEY}" "Publisher"        "${APP_PUBLISHER}"
    WriteRegStr HKLM "${UNINSTALL_KEY}" "InstallLocation"  "$INSTDIR"
    WriteRegStr HKLM "${UNINSTALL_KEY}" "UninstallString"  '"$INSTDIR\Uninstall.exe"'
    WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoModify"       1
    WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoRepair"       1

    ; Start Menu shortcut
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortcut  "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" \
                    "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0 \
                    SW_SHOWNORMAL "" "Calculate MSME interest on delayed vendor payments"
    CreateShortcut  "$SMPROGRAMS\${APP_NAME}\Uninstall.lnk" \
                    "$INSTDIR\Uninstall.exe"

    ; Desktop shortcut
    CreateShortcut  "$DESKTOP\${APP_NAME}.lnk" \
                    "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0 \
                    SW_SHOWNORMAL "" "MSMED Act Interest Calculator"
SectionEnd

; ── Uninstall Section ─────────────────────────────────────────────────────────
Section "Uninstall"
    ; Remove installed files
    Delete "$INSTDIR\${APP_EXE}"
    Delete "$INSTDIR\README.md"
    Delete "$INSTDIR\Sample File.xlsx"
    Delete "$INSTDIR\Uninstall.exe"
    RMDir  "$INSTDIR"

    ; Remove shortcuts
    Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
    Delete "$SMPROGRAMS\${APP_NAME}\Uninstall.lnk"
    RMDir  "$SMPROGRAMS\${APP_NAME}"
    Delete "$DESKTOP\${APP_NAME}.lnk"

    ; Remove registry entries
    DeleteRegKey HKLM "${UNINSTALL_KEY}"
SectionEnd
