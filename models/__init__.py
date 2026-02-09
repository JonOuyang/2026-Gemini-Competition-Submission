"""
CLOVIS Models - LLM integration and routing.
"""
from models.models import call_gemini, store_screenshot, get_stored_screenshot, GeminiModel
from models.function_calls import (
    ROUTER_TOOLS,
    ROUTER_TOOL_MAP,
    TOOL_CONFIG,
    # Legacy aliases
    RAPID_RESPONSE_TOOLS,
    RAPID_RESPONSE_TOOL_MAP,
)
from models.prompts import RAPID_RESPONSE_SYSTEM_PROMPT
