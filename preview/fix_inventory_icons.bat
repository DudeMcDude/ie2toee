@echo off
rem Clear leftover IE green from converted inventory icons already installed in a ToEE copy.
rem Usage: fix_inventory_icons.bat "C:\path\to\ToEE copy"
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Usage: fix_inventory_icons.bat "C:\path\to\ToEE copy"
  exit /b 1
)
set PY=python
where py >nul 2>nul && set PY=py -3
set SCRIPT=
if exist "%~dp0converter\fix_inventory_icons.py" set SCRIPT=%~dp0converter\fix_inventory_icons.py
if exist "%~dp0..\proto\fix_inventory_icons.py" set SCRIPT=%~dp0..\proto\fix_inventory_icons.py
if "%SCRIPT%"=="" (
  echo fix_inventory_icons.py not found (expected in converter\ or ..\proto\).
  exit /b 1
)
%PY% "%SCRIPT%" "%~1"
if errorlevel 1 exit /b 1
echo Done. Reopen the inventory to see the equipped-slot icons without the green background.
endlocal
