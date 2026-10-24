@echo off
rem Icewind Dale in ToEE - preview converter. Usage:
rem   convert.bat "C:\path\to\Icewind Dale (or Icewind Dale Enhanced Edition)" "C:\path\to\ToEE copy"
setlocal
cd /d "%~dp0"
if "%~2"=="" (
  echo Usage: convert.bat "C:\path\to\Icewind Dale" "C:\path\to\ToEE"
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
%PY% converter\ie2toee_preview.py --iwd "%~1" --toee "%~2" --tp TemplePlus --out output --install
if errorlevel 1 ( echo Conversion FAILED - see the messages above. & exit /b 1 )
echo.
echo Done. In TemplePlus\TemplePlusConfig.exe pick the module "IWD", then start a NEW game in TemplePlus\TemplePlus.exe.
endlocal
