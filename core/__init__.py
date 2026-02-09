"""
Core utilities and settings for CLOVIS.
"""
from core.settings import (
    get_host,
    get_port,
    set_host_and_port,
    get_screen_size,
    set_screen_size,
    get_viewport_size,
    set_viewport_size,
    get_model_configs,
    get_rapid_response_model,
    get_clovis_model,
)
from core.registry import (
    register_box,
    register_text,
    remove_entry,
    snapshot,
    clear,
)
