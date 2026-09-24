"""Load fixed sibling skill implementations from source or the staged runtime."""
import importlib.util
import sys
from pathlib import Path

_MODULES = {
    "ocr": ("iflytek-pdf-image-ocr", "image_ocr.py"),
    "translate": ("iflytek-translate", "translate.py"),
    "image": ("iflytek-image-understanding", "image_understanding.py"),
}

def skill_module(name):
    skill, filename = _MODULES[name]
    module_name = "_contract_ifly_" + name
    if module_name not in sys.modules:
        source = Path(__file__).resolve().parents[3] / "skills" / skill / "scripts" / filename
        spec = importlib.util.spec_from_file_location(module_name, source)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(module_name, None)
            raise
    return sys.modules[module_name]