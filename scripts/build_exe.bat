@echo off
echo ========================================
echo AuditBee PyInstaller 打包脚本
echo ========================================

set PROJECT_ROOT=%~dp0..
cd /d %PROJECT_ROOT%

echo.
echo [1/7] 构建前端...
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
echo [2/7] 复制前端静态文件到后端...
if exist ..\backend\static rmdir /s /q ..\backend\static
xcopy /E /I /Y build ..\backend\static
if errorlevel 1 (
    echo 复制静态文件失败
    pause
    exit /b 1
)

cd /d %PROJECT_ROOT%

echo.
echo [3/7] 安装 PyInstaller...
pip install pyinstaller
if errorlevel 1 (
    echo PyInstaller 安装失败
    pause
    exit /b 1
)

echo.
echo [4/7] 打包应用程序...
REM Temporarily swap .env with .env.example to avoid bundling real API keys
if exist config\.env (
    copy config\.env config\.env.bak >nul
    copy config\.env.example config\.env >nul
    echo   Temporarily replaced .env with .env.example for secure bundling
)
pyinstaller scripts\build.spec --clean --noconfirm
set PYINSTALLER_EXIT=%ERRORLEVEL%
REM Restore original .env
if exist config\.env.bak (
    copy config\.env.bak config\.env >nul
    del config\.env.bak
    echo   Restored original .env
)
if %PYINSTALLER_EXIT% neq 0 (
    echo 打包失败
    pause
    exit /b 1
)

REM Defense-in-depth: remove any .env.bak that may have been bundled
if exist dist\AuditBee\_internal\config\.env.bak del dist\AuditBee\_internal\config\.env.bak
if exist dist\AuditBee\config\.env.bak del dist\AuditBee\config\.env.bak

REM Clean test files and dev artifacts from distribution
if exist dist\AuditBee\_internal\agent\tests rmdir /s /q dist\AuditBee\_internal\agent\tests
if exist dist\AuditBee\_internal\agent\pytest.ini del dist\AuditBee\_internal\agent\pytest.ini
REM Clean __pycache__ and .pytest_cache directories (dev artifacts)
for /r dist\AuditBee\_internal /d %%d in (__pycache__) do rmdir /s /q "%%d" 2>nul
for /r dist\AuditBee\_internal /d %%d in (.pytest_cache) do rmdir /s /q "%%d" 2>nul

echo.
echo [5/7] Creating runtime directories...
mkdir dist\AuditBee\config 2>nul
mkdir dist\AuditBee\data\database 2>nul
mkdir dist\AuditBee\data\documents 2>nul
mkdir dist\AuditBee\data\processed 2>nul
mkdir dist\AuditBee\data\reports 2>nul
mkdir dist\AuditBee\data\logs 2>nul
mkdir dist\AuditBee\data\kg_output 2>nul
mkdir dist\AuditBee\data\kg_input 2>nul
copy config\.env.example dist\AuditBee\config\.env >nul
copy config\.env.example dist\AuditBee\config\.env.example >nul
echo   Done.

echo.
echo [6/7] Copying pre-built LightRAG index...
if exist graphrag_index\lightrag_output (
    xcopy /E /I /Y graphrag_index\lightrag_output dist\AuditBee\_internal\graphrag_index\lightrag_output >nul
    echo   Pre-built LightRAG index copied.
) else (
    echo   WARNING: graphrag_index/lightrag_output/ not found. Knowledge graph will need to be rebuilt.
)

echo.
echo [7/7] Copying embedding model...
if exist model (
    xcopy /E /I /Y model dist\AuditBee\model
    echo   Embedding model copied.
) else (
    echo   WARNING: model/ directory not found. User must download manually.
)

echo.
echo ========================================
echo 打包完成！
echo 输出目录: dist\AuditBee\
echo ========================================
echo.
echo 使用方法:
echo 1. 将 dist\AuditBee 目录复制到目标机器
echo 2. 运行 AuditBee.exe，启动器将引导配置 LLM API Key
echo 3. 启动器中可选下载嵌入模型（知识图谱功能需要）
echo 4. 配置完成后将自动打开浏览器
echo 5. 高级用户可使用 --no-launcher 跳过启动器
echo.
pause
