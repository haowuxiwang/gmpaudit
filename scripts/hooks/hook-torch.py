# Custom PyInstaller hook for torch
# Overrides the default hook-torch.py to avoid collecting all submodules
# (which causes a subprocess crash with PyTorch 2.x on Windows)
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

# Collect only data files and binaries, skip submodule collection
datas = collect_data_files('torch', excludes=['test', 'test.*', 'testing', 'testing.*'])
binaries = collect_dynamic_libs('torch')

# Minimal hidden imports - only what's actually needed
hiddenimports = [
    'torch',
    'torch.nn',
    'torch.nn.functional',
    'torch.optim',
    'torch.utils',
    'torch.utils.data',
    'torch.cuda',
    'torch.backends',
    'torch.backends.cuda',
    'torch.autograd',
]
