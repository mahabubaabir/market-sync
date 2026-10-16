@echo off
rem Market Sync — Windows 10/11 build (run from any Windows machine)
rem Output: dist\MarketSync-<version>-win64.exe
setlocal enabledelayedexpansion
cd /d "%~dp0.."

echo == Market Sync Windows build ==
where py >nul 2>nul || (echo Python launcher "py" not found. Install Python 3.10+ from python.org & exit /b 1)

echo [1/4] installing build dependencies...
py -3 -m pip install --upgrade pip >nul
py -3 -m pip install -r requirements.txt pyinstaller pillow tzdata || goto :err

echo [2/4] rendering icon.ico...
py -3 tools\make_ico.py || goto :err

echo [3/4] building exe (this takes a few minutes)...
py -3 -m PyInstaller --noconfirm tools\market-sync.spec || goto :err

echo [4/4] naming with version...
for /f "delims=" %%v in ('py -3 -c "import config;print(config.APP_VERSION)"') do set VER=%%v
copy /y dist\MarketSync.exe "dist\MarketSync-!VER!-win64.exe" >nul || goto :err

echo.
echo Built: dist\MarketSync-!VER!-win64.exe
echo Share it on the GitHub release page (same release as the Linux .deb).
exit /b 0

:err
echo.
echo BUILD FAILED — see the messages above.
exit /b 1
