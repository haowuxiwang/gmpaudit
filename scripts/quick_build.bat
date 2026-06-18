@echo off
REM Quick build script for AuditBee
REM Usage: scripts\quick_build.bat [--no-model]

set PROJECT_ROOT=%~dp0..
cd /d %PROJECT_ROOT%

echo ========================================
echo AuditBee Quick Build
echo ========================================

REM Kill any running AuditBee processes
taskkill /F /IM AuditBee.exe 2>nul
timeout /t 1 /nobreak >nul

echo.
echo [1/4] Building frontend...
cd frontend
call npm run build
if errorlevel 1 (
    echo Frontend build failed!
    pause
    exit /b 1
)
cd ..

echo.
echo [2/4] Copying frontend static files...
if exist backend\static rmdir /s /q backend\static
xcopy /E /I /Y frontend\build backend\static >nul

echo.
echo [3/4] Running PyInstaller...
pyinstaller scripts\build.spec --noconfirm
if errorlevel 1 (
    echo PyInstaller failed!
    pause
    exit /b 1
)

echo.
echo [4/4] Copying embedding model...
if "%1"=="--no-model" (
    echo   Skipped [--no-model flag].
) else (
    if exist model (
        xcopy /E /I /Y model dist\AuditBee\model >nul
        echo   Model copied.
    ) else (
        echo   WARNING: model\ directory not found.
    )
)

echo.
echo ========================================
echo Build complete!
echo Output: dist\AuditBee\
echo ========================================
pause
