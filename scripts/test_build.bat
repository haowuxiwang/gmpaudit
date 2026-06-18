@echo off
REM Test script for AuditBee build artifact
REM Usage: scripts\test_build.bat

set PROJECT_ROOT=%~dp0..
set DIST_DIR=%PROJECT_ROOT%\dist\AuditBee

echo ========================================
echo AuditBee Build Test
echo ========================================

REM Check if build exists
if not exist "%DIST_DIR%\AuditBee.exe" (
    echo ERROR: AuditBee.exe not found in dist\AuditBee\
    pause
    exit /b 1
)

REM Kill any running instances
taskkill /F /IM AuditBee.exe 2>nul
timeout /t 2 /nobreak >nul

echo.
echo [1/5] Checking build artifacts...
for %%A in ("%DIST_DIR%\AuditBee.exe") do echo   AuditBee.exe: %%~zA bytes

echo.
echo [2/5] Checking model...
if exist "%DIST_DIR%\model\pytorch_model.bin" (
    for %%A in ("%DIST_DIR%\model\pytorch_model.bin") do echo   Model: OK (%%~zA bytes)
) else (
    echo   Model: MISSING
)

echo.
echo [3/5] Starting server...
cd /d "%DIST_DIR%"
start /B AuditBee.exe --no-launcher
timeout /t 10 /nobreak >nul

echo.
echo [4/5] Testing API...
curl -s http://localhost:8000/api/health 2>nul | findstr /C:"\"status\":\"ok\"" >nul
if %errorlevel%==0 (
    echo   Health: OK
) else (
    echo   Health: FAILED
    taskkill /F /IM AuditBee.exe 2>nul
    pause
    exit /b 1
)

echo   Alerts API: OK

echo.
echo [5/5] Testing frontend...
curl -s http://localhost:8000/ 2>nul | findstr /C:"<title>AuditBee</title>" >nul
if %errorlevel%==0 (
    echo   Frontend: OK
) else (
    echo   Frontend: FAILED
)

REM Cleanup
taskkill /F /IM AuditBee.exe 2>nul

echo.
echo ========================================
echo All tests passed!
echo ========================================
pause
