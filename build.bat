@echo off
rem Builds MacroPad.exe and (if Inno Setup is installed) MacroPad-Setup-x.y.z.exe on your PC.
rem Normally GitHub builds everything for you - this is for testing without GitHub.
setlocal
cd /d "%~dp0"

echo === Python 3.12 ===
py -V:3.12 --version >nul 2>&1
if errorlevel 1 (
  echo Python 3.12 is not installed - installing it with the Python install manager...
  py install 3.12
  if errorlevel 1 goto :fail
)

if not exist .venv\Scripts\python.exe (
  py -V:3.12 -m venv .venv
  if errorlevel 1 goto :fail
)
set PY=.venv\Scripts\python.exe

echo === Libraries ===
%PY% -m pip install --upgrade pip >nul
%PY% -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :fail

echo === Background previews (needs g++, e.g. from MSYS2 / MinGW-w64) ===
where g++ >nul 2>&1
if errorlevel 1 (
  echo g++ not found - the app will show still backgrounds instead of the animated previews.
) else (
  %PY% tools\build_bgfx.py
  if errorlevel 1 goto :fail
)

echo === Tests ===
%PY% -m unittest discover -s tests
if errorlevel 1 goto :fail

echo === App ===
%PY% tools\make_icon.py app\macropad_app\resources
%PY% -m PyInstaller --noconfirm macropad.spec
if errorlevel 1 goto :fail
for /f %%v in ('%PY% -c "import sys; sys.path.insert(0,'app'); import macropad_app; print(macropad_app.VERSION)"') do set APPVER=%%v
for /f %%v in ('%PY% -c "import json; print(json.load(open('app/macropad_app/resources/firmware/firmware.json'))['version'])"') do set FWVER=%%v
%PY% tools\make_manifest.py files dist\MacroPad %APPVER% %FWVER%

echo === Installer ===
set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" (
  echo Inno Setup 6 not found - the app is ready in dist\MacroPad\MacroPad.exe
  echo For the Setup.exe install Inno Setup from https://jrsoftware.org/isdl.php and run this again.
  goto :done
)
"%ISCC%" /DMyAppVersion=%APPVER% installer\macropad.iss
if errorlevel 1 goto :fail
%PY% tools\make_manifest.py release dist\MacroPad dist\MacroPad-Setup-%APPVER%.exe dist\manifest.json
echo.
echo Done: dist\MacroPad-Setup-%APPVER%.exe

:done
pause
exit /b 0

:fail
echo.
echo Build failed - see the messages above.
pause
exit /b 1
