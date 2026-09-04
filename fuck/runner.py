"""
TheFuck CLI Runner for Kapsel.
Provides seamless execution of thefuck with automatic compatibility shims for Python 3.12+.
All comments and descriptions are in English.
"""

import importlib.machinery
import importlib.util
import sys
import types

# Ensure backward compatibility for Python 3.12+ where the legacy 'imp' module was removed
if "imp" not in sys.modules:
    imp = types.ModuleType("imp")

    def _load_source(modname: str, filename: str):
        loader = importlib.machinery.SourceFileLoader(modname, str(filename))
        spec = importlib.util.spec_from_file_location(modname, str(filename), loader=loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        return module

    imp.load_source = _load_source
    sys.modules["imp"] = imp

from thefuck.entrypoints.main import main


if __name__ == "__main__":
    main()
