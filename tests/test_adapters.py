from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from e2e_verification.adapters import load_adapter
from e2e_verification.workflow import HarnessRegistry


class AdapterTest(unittest.TestCase):
    def test_adapter_registers_profile_harnesses(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "adapter.py"
            path.write_text(
                "def register_harnesses(registry):\n"
                "    registry.register('synthetic-check', lambda step, out: None)\n",
                encoding="utf-8",
            )
            registry = HarnessRegistry()
            load_adapter(path, registry)
            self.assertEqual(["synthetic-check"], registry.names())

    def test_adapter_without_registration_hook_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "adapter.py"
            path.write_text("VALUE = 1\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "register_harnesses"):
                load_adapter(path, HarnessRegistry())


if __name__ == "__main__":
    unittest.main()
