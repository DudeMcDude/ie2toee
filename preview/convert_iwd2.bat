@echo off
rem Icewind Dale II (Targos) in ToEE - proof-of-concept converter. Usage:
rem   convert_iwd2.bat "C:\path\to\Icewind Dale 2" "C:\path\to\ToEE copy"
setlocal
cd /d "%~dp0"
if "%~2"=="" (
  echo Usage: convert_iwd2.bat "C:\path\to\Icewind Dale 2" "C:\path\to\ToEE copy"
  echo See README.txt.
  exit /b 1
)
set PY=python
where py >nul 2>nul && set PY=py -3
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" || (
  echo Python 3.9 or newer is needed: https://www.python.org/downloads/  ^(tick "Add python.exe to PATH"^)
  exit /b 1
)
%PY% -m pip install --user --disable-pip-version-check -q -r converter\requirements.txt || exit /b 1
%PY% converter\ie2toee_preview_iwd2.py --iwd2 "%~1" --toee "%~2" --tp TemplePlus --out output --install
if errorlevel 1 ( echo Conversion FAILED - see the messages above. & exit /b 1 )
echo.
echo Done. Start a NEW game with TemplePlus\TemplePlus.exe (module ToEE): it begins at the Targos docks.
endlocal
