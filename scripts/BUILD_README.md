# AuditBee Build Scripts

## Quick Build

### Windows
```cmd
scripts\quick_build.bat
scripts\quick_build.bat --no-model
```

### Linux/Mac
```bash
./scripts/quick_build.sh
./scripts/quick_build.sh --no-model
```

## Test Build

### Windows
```cmd
scripts\test_build.bat
```

### Linux/Mac
```bash
./scripts/test_build.sh
```

## Manual Build Steps

1. Build frontend:
   ```bash
   cd frontend && npm run build
   ```

2. Copy static files:
   ```bash
   rm -rf backend/static
   cp -r frontend/build backend/static
   ```

3. Run PyInstaller:
   ```bash
   pyinstaller scripts/build.spec --noconfirm
   ```

4. Copy model:
   ```bash
   cp -r model dist/AuditBee/model
   ```

## Output

Build artifacts are in `dist/AuditBee/`:
- `AuditBee.exe` - Main executable
- `_internal/` - Python runtime and dependencies
- `model/` - Embedding model (optional)
- `data/` - Runtime data (created on first run)
- `config/` - Configuration files

## Troubleshooting

### Build fails with "Permission Error"
- Close any running AuditBee.exe processes
- Wait a few seconds and retry

### Model not found
- Ensure `model/` directory exists in project root
- Or use `--no-model` flag to skip model copying

### Frontend not loading
- Ensure `frontend/build/` exists
- Re-run `npm run build` in frontend directory
