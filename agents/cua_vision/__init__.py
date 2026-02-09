"""
CUA Vision Agent - Desktop control via screen understanding + mouse/keyboard.

This agent can see the user's screen and interact with it by:
- Clicking UI elements based on visual recognition
- Typing and keyboard input
- Reading on-screen content
- GUI automation via vision models
- Visual verification of actions
"""
from agents.cua_vision.agent import (
    VisionAgent,
    start_interact_with_screen,
    look_at_screen_and_respond,
    watch_screen_and_respond,
)
from agents.cua_vision.tools import (
    VISION_TOOLS,
    VISION_TOOL_MAP,
    TOOL_CONFIG,
    reset_state,
    get_memory,
    remember_information,
    find_and_click_element,
    go_to_element,
    crop_and_search,
)
from integrations.audio import tts_speak
from agents.cua_vision.keyboard import (
    move_cursor,
    type_string,
    press_ctrl_hotkey,
    press_alt_hotkey,
    click_left_click,
    click_double_left_click,
    click_right_click,
)
from agents.cua_vision.prompts import (
    VISION_AGENT_SYSTEM_PROMPT,
    LOOK_AT_SCREEN_PROMPT,
    WATCH_SCREEN_PROMPT,
)
