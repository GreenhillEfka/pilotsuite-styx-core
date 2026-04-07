"""OpenAI-compatible API bridge.

Keeps the registry import path `copilot_core.api.v1.openai_compat` stable while
reusing the runtime implementation from `conversation.py`.
"""

from copilot_core.api.v1.conversation import openai_compat_bp

__all__ = ["openai_compat_bp"]
