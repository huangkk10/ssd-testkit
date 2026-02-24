import sys, os
os.environ.pop("PYTHONPATH", None)
_meipass = getattr(sys, "_MEIPASS", "")
_exe_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else ""
_keep = {p for p in [_meipass, _exe_dir] if p}
# Normalise _MEIPASS once for sub-path comparisons.
# We must preserve paths *inside* _MEIPASS (e.g. base_library.zip) so that
# PyInstaller's own runtime hooks (pyi_rth_inspect, etc.) can still import
# stdlib modules stored there.  Stripping those paths caused:
#   ModuleNotFoundError: No module named 'linecache'
_meipass_norm = os.path.normpath(_meipass) + os.sep if _meipass else None
sys.path = [
    p for p in sys.path
    if p in _keep
    or p == ""
    or (_meipass_norm and os.path.normpath(p).startswith(_meipass_norm))
]
for _d in [_exe_dir, _meipass]:
    if _d and _d not in sys.path:
        sys.path.append(_d)
_prefixes = ("framework", "lib", "tests", "path_manager")
_evict = [n for n,m in list(sys.modules.items()) if any(n==p or n.startswith(p+".") for p in _prefixes) and getattr(m,"__file__","") and not any(getattr(m,"__file__","").startswith(d) for d in _keep)]
for _n in _evict:
    del sys.modules[_n]
