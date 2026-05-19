@echo off
echo ========================================
echo AuditBee PyInstaller 打包脚本
echo ========================================

set PROJECT_ROOT=%~dp0..
cd /d %PROJECT_ROOT%

echo.
echo [1/4] 构建前端...
cd frontend
call npm install
if errorlevel 1 (
    echo 前端依赖安装失败
    pause
    exit /b 1
)

call npm run build
if errorlevel 1 (
    echo 前端构建失败
    pause
    exit /b 1
)

echo.
echo [2/4] 复制前端静态文件到后端...
if exist ..\backend\static rmdir /s /q ..\backend\static
xcopy /E /I /Y build ..\backend\static
if errorlevel 1 (
    echo 复制静态文件失败
    pause
    exit /b 1
)

cd /d %PROJECT_ROOT%

echo.
echo [3/4] 安装 PyInstaller...
pip install pyinstaller
if errorlevel 1 (
    echo PyInstaller 安装失败
    pause
    exit /b 1
)

echo.
echo [4/4] 打包应用程序...
pyinstaller scripts\build.spec --clean --noconfirm
if errorlevel 1 (
    echo 打包失败
    pause
    exit /b 1
)

echo.
echo [5/5] Creating runtime directories...
mkdir dist\AuditBee\_internal\data\database 2>nul
mkdir dist\AuditBee\_internal\data\documents 2>nul
mkdir dist\AuditBee\_internal\data\processed 2>nul
mkdir dist\AuditBee\_internal\data\reports 2>nul
mkdir dist\AuditBee\_internal\data\logs 2>nul
copy config\.env.example dist\AuditBee\_internal\config\.env >nul
echo   Done.

echo.
echo ========================================
echo 打包完成！
echo 输出目录: dist\AuditBee\
echo ========================================
echo.
echo 使用方法:
echo 1. 将 dist\AuditBee 目录复制到目标机器
echo 2. 编辑 config\.env 添加 API 密钥
echo 3. 运行 AuditBee.exe
echo 4. 首次运行会自动下载 embedding 模型（约1.3GB）
echo.
pause
