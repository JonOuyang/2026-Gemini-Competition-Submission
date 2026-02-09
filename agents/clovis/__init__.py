"""
CLOVIS Agent - Screen annotation and explanation.

This agent can see the user's screen and draw annotations (boxes, text, pointers)
to explain or highlight elements. It's the visual explanation component of CLOVIS.
"""
from agents.clovis.agent import ClovisAgent
from agents.clovis.tools import (
    CLOVIS_TOOLS,
    CLOVIS_TOOL_MAP,
    draw_bounding_box,
    draw_pointer_to_object,
    create_text,
    create_text_for_box,
    clear_screen,
    destroy_box,
    destroy_text,
    direct_response,
)
from agents.clovis.prompts import CLOVIS_SYSTEM_PROMPT
