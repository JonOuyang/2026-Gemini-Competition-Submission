registry = {}

"""
registry entries are stored as 
    Box: {id: [type = "box", x_min, y_min, x_max, y_max]}
    Text: {id: [type = "text", x_pos, y_pos]}

"""

def register_box(box_id: str, x_min: int, y_min: int, x_max: int, y_max: int):
    registry[box_id] = {
        "type": "box",
        "x_min": x_min,
        "y_min": y_min,
        "x_max": x_max,
        "y_max": y_max,
    }

def register_text(text_id: str, x_pos: int, y_pos: int):
    registry[text_id] = {
        "type": "text",
        "x": x_pos,
        "y": y_pos,
    }

def remove_entry(entry_id: str) -> bool:
    return registry.pop(entry_id, None) is not None

def snapshot() -> dict:
    return dict(registry)

def clear() -> None:
    registry.clear()
