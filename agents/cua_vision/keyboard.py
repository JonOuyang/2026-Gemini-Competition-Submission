"""
CUA Vision Agent - Keyboard and Mouse Control

Provides functions for emulating keyboard and mouse input.
"""
import time
import platform
import pyautogui


# ================================================================================
# TYPING FUNCTIONS
# ================================================================================

def type_string(string: str, submit: bool = False):
    """Types out a string.

    Args:
        string: The argument should be passed as a multiline string
        submit: Whether to press Enter once after typing
    """
    # Manual backslash error reassignment
    string = string.replace("\\'", "\'")
    string = string.replace('\\\\', '\\')
    string = string.replace('\\n', '\n')
    string = string.replace('\\r', '\r')
    string = string.replace('\\t', '\t')
    string = string.replace('\\b', '\b')
    string = string.replace('\\f', '\f')

    pyautogui.write(string, interval=0.01)
    if submit:
        pyautogui.press('enter')


# ================================================================================
# CURSOR POSITIONING
# ================================================================================

def move_cursor(x: float, y: float, duration: float = 0.2):
    """Move the mouse cursor to a screen coordinate."""
    pyautogui.moveTo(x=x, y=y, duration=duration)


# ================================================================================
# MOUSE CLICK FUNCTIONS
# ================================================================================

def click_left_click():
    """Emulate a mouse left click at the current cursor position."""
    pyautogui.click(clicks=1, button='left')


def hold_down_left_click(x: float, y: float):
    """Emulates a mouse held down left click.

    Args:
        x: x coordinate on screen of where you want to click
        y: y coordinate on screen of where you want to click
    """
    pyautogui.mouseDown('left')


def hold_down_right_click(x: float, y: float):
    """Emulates a mouse held down right click.

    Args:
        x: x coordinate on screen of where you want to click
        y: y coordinate on screen of where you want to click
    """
    pyautogui.mouseDown('right')


def release_left_click(x: float, y: float):
    """Emulates releasing the mouse left click button.

    Args:
        x: x coordinate on screen of where you want to click
        y: y coordinate on screen of where you want to click
    """
    pyautogui.mouseUp('left')


def release_right_click(x: float, y: float):
    """Emulates releasing the mouse right click button.

    Args:
        x: x coordinate on screen of where you want to click
        y: y coordinate on screen of where you want to click
    """
    pyautogui.mouseUp('right')


def click_double_left_click():
    """Emulate a mouse double (left) click at the current cursor position."""
    pyautogui.click(clicks=2, interval=0.1, button='left')


def click_right_click():
    """Emulate a mouse right click at the current cursor position."""
    pyautogui.click(clicks=1, button='right')


# ================================================================================
# KEY PRESS FUNCTIONS
# ================================================================================

def press_key_for_duration(key: str, seconds: float) -> None:
    """Holds down a key for a specified duration.

    Args:
        key: The key to be pressed down. Can be any alphanumeric key on the keyboard
        seconds: The amount of time to be pressed down in seconds
    """
    pyautogui.keyDown(key)
    time.sleep(seconds)
    pyautogui.keyUp(key)
    print(f'Key chosen: {key}')
    print(f'Key held down for {seconds}s')


def hold_down_key(key: str) -> None:
    """Press down a key indefinitely until otherwise told.

    Args:
        key: The key to be pressed down. The key must be one of the following 'w', 'a', 's', 'd'
    """
    pyautogui.keyDown(key)


def release_held_key(key: str) -> None:
    """Release a previously held down key.

    Args:
        key: The key to be pressed down. The key must be one of the following 'w', 'a', 's', 'd'
    """
    pyautogui.keyUp(key)


def press_ctrl_hotkey(key: str):
    """Press a control-style hotkey.

    On macOS, many app-launcher and system shortcuts use Command instead of
    Control, so we transparently map ctrl -> command.

    Args:
        key: The key to be pressed along with control
    """
    modifier = 'command' if platform.system() == 'Darwin' else 'ctrl'
    pyautogui.hotkey(modifier, key)


def press_alt_hotkey(key: str):
    """Press down a key along with the alt key to emulate a hotkey.

    Args:
        key: The key to be pressed along with alt
    """
    pyautogui.hotkey('alt', key)


def press_command_hotkey(key: str):
    """Press down a key along with the command key to emulate a hotkey."""
    pyautogui.hotkey('command', key)


def press_hotkey_combo(keys: str):
    """
    Press a multi-key combo simultaneously.

    Accepted formats:
    - "command+shift+4"
    - "ctrl + alt + delete"
    - "cmd,space"
    """
    if not isinstance(keys, str) or not keys.strip():
        raise ValueError("keys must be a non-empty string like 'command+shift+4'")

    normalized = keys.replace(",", "+")
    raw_parts = [part.strip().lower() for part in normalized.split("+") if part.strip()]
    if len(raw_parts) < 2:
        raise ValueError("hotkey combo must include at least two keys")

    aliases = {
        "cmd": "command",
        "command": "command",
        "meta": "command",
        "super": "command",
        "ctrl": "ctrl",
        "control": "ctrl",
        "alt": "alt",
        "option": "alt",
        "shift": "shift",
        "enter": "enter",
        "return": "enter",
        "esc": "esc",
        "escape": "esc",
        "space": "space",
        "tab": "tab",
        "del": "delete",
    }
    resolved = [aliases.get(part, part) for part in raw_parts]
    pyautogui.hotkey(*resolved)
