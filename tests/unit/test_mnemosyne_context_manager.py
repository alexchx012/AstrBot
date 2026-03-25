from pathlib import Path
import sys
from unittest.mock import MagicMock

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = PROJECT_ROOT / "data" / "plugins"
PLUGIN_PACKAGE_ROOT = PLUGIN_ROOT / "astrbot_plugin_mnemosyne"

if not PLUGIN_PACKAGE_ROOT.exists():
    pytest.skip(
        "astrbot_plugin_mnemosyne plugin source not present in data/plugins",
        allow_module_level=True,
    )

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from astrbot_plugin_mnemosyne.memory_manager.context_manager import (  # noqa: E402
    ConversationContextManager,
)


def test_init_conv_does_not_mutate_original_contexts():
    manager = ConversationContextManager()
    original_contexts = [{"role": "assistant", "content": "history"}]

    manager.init_conv("session-1", original_contexts, MagicMock())
    manager.add_message("session-1", "user", "hello")

    assert original_contexts == [{"role": "assistant", "content": "history"}]
    assert len(manager.get_history("session-1")) == 2
