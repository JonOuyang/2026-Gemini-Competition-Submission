import json
import os
import socket
from typing import Tuple, Union

DEFAULT_SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "..", "settings.json")


# ================================================================================================
# HOST AND PORT
# ================================================================================================

def _is_port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return sock.connect_ex((host, port)) != 0


def set_host_and_port(settings_path: str = DEFAULT_SETTINGS_PATH) -> tuple[str, int]:
    with open(settings_path, "r", encoding="utf-8") as handle:
        settings = json.load(handle)

    host = settings.get("host", "127.0.0.1")
    preferred_port = int(settings.get("port", 8765))
    if _is_port_free(host, preferred_port):
        port = preferred_port
    else:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((host, 0))
            port = sock.getsockname()[1]

    settings["host"] = host
    settings["port"] = port
    with open(settings_path, "w", encoding="utf-8") as handle:
        json.dump(settings, handle, indent=4)

    return host, port


def get_host(settings_path: str = DEFAULT_SETTINGS_PATH) -> str:
    with open(settings_path, "r", encoding="utf-8") as handle:
        settings = json.load(handle)
    return settings["host"]


def get_port(settings_path: str = DEFAULT_SETTINGS_PATH) -> int:
    with open(settings_path, "r", encoding="utf-8") as handle:
        settings = json.load(handle)
    return settings["port"]


# ================================================================================================
# SCREEN SIZE
# ================================================================================================

def set_screen_size(screen_width: int, screen_height: int, settings_path: str = DEFAULT_SETTINGS_PATH) -> None:
    with open(settings_path, "r", encoding="utf-8") as handle:
        settings = json.load(handle)

    settings["screen_width"] = screen_width
    settings["screen_height"] = screen_height

    with open(settings_path, "w", encoding="utf-8") as handle:
        json.dump(settings, handle, indent=4)


def get_screen_size(settings_path: str = DEFAULT_SETTINGS_PATH) -> tuple[int, int]:
    with open(settings_path, "r", encoding="utf-8") as handle:
        settings = json.load(handle)
    return (settings["screen_width"], settings["screen_height"])


def set_viewport_size(viewport_width: int, viewport_height: int, settings_path: str = DEFAULT_SETTINGS_PATH) -> None:
    with open(settings_path, "r", encoding="utf-8") as handle:
        settings = json.load(handle)

    settings["viewport_width"] = viewport_width
    settings["viewport_height"] = viewport_height

    with open(settings_path, "w", encoding="utf-8") as handle:
        json.dump(settings, handle, indent=4)


def get_viewport_size(settings_path: str = DEFAULT_SETTINGS_PATH) -> tuple[int, int]:
    with open(settings_path, "r", encoding="utf-8") as handle:
        settings = json.load(handle)
    return (settings["viewport_width"], settings["viewport_height"])


# ================================================================================================
# MODEL CONFIG
# ================================================================================================

def get_model_configs(settings_path: str = DEFAULT_SETTINGS_PATH) -> tuple[str, str]:
    """Get both model configurations: (rapid_response_model, clovis_model)"""
    with open(settings_path, "r", encoding="utf-8") as handle:
        settings = json.load(handle)
    return (
        settings.get("rapid_response_model", "gemini-flash-lite-latest"),
        settings.get("clovis_model", "gemini-3-flash-preview")
    )


def get_rapid_response_model(settings_path: str = DEFAULT_SETTINGS_PATH) -> str:
    with open(settings_path, "r", encoding="utf-8") as handle:
        settings = json.load(handle)
    return settings.get("rapid_response_model", "gemini-flash-lite-latest")


def get_clovis_model(settings_path: str = DEFAULT_SETTINGS_PATH) -> str:
    with open(settings_path, "r", encoding="utf-8") as handle:
        settings = json.load(handle)
    return settings.get("clovis_model", "gemini-3-flash-preview")


# ================================================================================================
# TTS CONFIG
# ================================================================================================

def get_tts_active_bool(settings_path: str = DEFAULT_SETTINGS_PATH) -> tuple[bool]:
    """Return tuple with boolean if TTS should be active or not"""
    with open(settings_path, "r", encoding="utf-8") as handle:
        settings = json.load(handle)
    return (settings.get("tts", False),)


# ================================================================================================
# PERSONALIZATION CONFIG
# ================================================================================================

def get_personalization_config(settings_path: str = DEFAULT_SETTINGS_PATH) -> Tuple[Union[str, bool]]:
    """Return tuple with personalization string or False if not set"""
    with open(settings_path, "r", encoding="utf-8") as handle:
        settings = json.load(handle)
    return (settings.get("personalization", False),)
