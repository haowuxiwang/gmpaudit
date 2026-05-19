@echo off
echo ========================================
echo AuditBee Factory Reset
echo ========================================
echo.
echo This will reset AuditBee to factory defaults.
echo.
echo WILL BE DELETED:
echo   - Database (data\database\)
echo   - Logs (data\logs\)
echo   - Uploaded documents (data\documents\)
echo   - Generated reports (data\reports\)
echo   - Processed files (data\processed\)
echo   - User config (config\.env)
echo   - GraphRAG logs and cache
echo.
echo WILL BE PRESERVED:
echo   - Embedding model (model\)
echo   - Knowledge graph index (graphrag_index\)
echo   - Config template (config\.env.example)
echo   - FFmpeg tools (tools\)
echo.

set /p confirm="Continue? (Y/N): "
if /i not "%confirm%"=="Y" (
    echo Cancelled.
    pause
    exit /b 0
)

set PROJECT_ROOT=%~dp0..
cd /d %PROJECT_ROOT%

echo.
echo [1/5] Cleaning database...
if exist data\database\gmp_audit.db del /f data\database\gmp_audit.db
if exist data\database\gmp_audit.db-shm del /f data\database\gmp_audit.db-shm
if exist data\database\gmp_audit.db-wal del /f data\database\gmp_audit.db-wal
if exist data\database\gmp_audit.db-journal del /f data\database\gmp_audit.db-journal
echo   Done.

echo.
echo [2/5] Cleaning logs and runtime data...
if exist data\logs del /s /f /q data\logs\* 2>nul
if exist data\documents del /s /f /q data\documents\* 2>nul
if exist data\reports del /s /f /q data\reports\* 2>nul
if exist data\processed del /s /f /q data\processed\* 2>nul
echo   Done.

echo.
echo [3/5] Cleaning user config...
if exist config\.env del /f config\.env
echo   Done.

echo.
echo [4/5] Cleaning GraphRAG cache and logs...
if exist graphrag_index\.env del /f graphrag_index\.env
if exist graphrag_index\logs del /s /f /q graphrag_index\logs\* 2>nul
if exist graphrag_index\lightrag_output\kv_store_llm_response_cache.json del /f graphrag_index\lightrag_output\kv_store_llm_response_cache.json
echo   Done.

echo.
echo [5/5] Regenerating config from template...
if exist config\.env.example copy config\.env.example config\.env >nul
echo   Done.

echo.
echo ========================================
echo Factory reset complete!
echo.
echo Preserved:
echo   - model\ (Embedding model)
echo   - graphrag_index\ (Knowledge graph)
echo   - tools\ffmpeg\ (FFmpeg)
echo.
echo Next steps:
echo   1. Edit config\.env to add your API keys
echo   2. Run scripts\start.bat to start AuditBee
echo ========================================
pause
