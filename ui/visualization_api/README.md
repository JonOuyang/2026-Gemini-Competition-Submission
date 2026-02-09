# Visualization API Protocol

This directory contains the Python-side callable helpers that send draw commands over the local WebSocket bridge to the Electron overlay.

## Commands (Python -> UI)

### draw_box
```json
{
  "command": "draw_box",
  "id": "box_123",
  "x": 200,
  "y": 160,
  "width": 260,
  "height": 140,
  "stroke": "#ff4d4d",
  "strokeWidth": 3,
  "fill": null,
  "opacity": 1.0
}
```

### remove_box
```json
{ "command": "remove_box", "id": "box_123" }
```

### draw_text
```json
{
  "command": "draw_text",
  "id": "text_123",
  "x": 120,
  "y": 80,
  "text": "Hello",
  "fontSize": 18,
  "fontFamily": "Helvetica",
  "align": "left",
  "baseline": "top"
}
```

### remove_text
```json
{ "command": "remove_text", "id": "text_123" }
```

### draw_dot
```json
{
  "command": "draw_dot",
  "id": "dot_1",
  "x": 400,
  "y": 300,
  "radius": 6,
  "color": "#00ffcc"
}
```

### remove_dot
```json
{ "command": "remove_dot", "id": "dot_1" }
```

### clear
```json
{ "command": "clear" }
```

## Events (UI -> Python)

### click
```json
{ "event": "click", "id": "box_123", "type": "box" }
```

### viewport
```json
{ "event": "viewport", "width": 2560, "height": 1600 }
```

### reset
```json
{ "event": "reset" }
```
