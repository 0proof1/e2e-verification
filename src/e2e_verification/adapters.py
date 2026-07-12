from __future__ import annotations

import importlib.util
from pathlib import Path

from .workflow import HarnessRegistry


def load_adapter(path: Path, registry: HarnessRegistry) -> None:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ValueError(f"adapter does not exist: {resolved}")
    module_name = f"e2e_verification_adapter_{abs(hash(str(resolved)))}"
    spec = importlib.util.spec_from_file_location(module_name, resolved)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load adapter: {resolved}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    register = getattr(module, "register_harnesses", None)
    if not callable(register):
        raise ValueError(f"adapter must define register_harnesses(registry): {resolved}")
    register(registry)

