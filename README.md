# CLOVIS
## Computer Linked Overlay Vision Interface System
> This is a public checkpoint. This is a limited version of the full code. Please do not expect production ready performance. Best experience with a paid Gemini API key.

## Installation

1. Clone GitHub repository
```
git clone https://github.com/JonOuyang/Jayu
```

2. Create your environment and install necessary dependencies 
```
./setup.sh
```

Or manually:
```
conda create -n clovis
conda activate clovis

pip install -r requirements.txt
cd ui && npm install
cd ../agents/cua_cli/gemini-cli && npm install && npm run build
```

3. Create your .env file for your keys
```
GEMINI_API_KEY = "YOUR_API_KEY"

ELEVENLABS_URL = "YOUR_API_KEY"
ELEVENLABS_API_KEY = "YOUR_API_KEY"
```

## Running Clovis

1. Run the frontend visualization
```
cd ui
npm run dev
```

2. Run the main app (in the project root directory)
```
python app.py
```

## Clovis Commands

* `Cmd + Shift + Space` opens the CLOVIS input bar
* `Cmd + Shift + C` stops active actions and clears overlay state

---

## System Architecture

### Overview

CLOVIS uses a **two-tier routing architecture** where a lightweight router model decides how to handle requests, then delegates to specialized agents for execution.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER INPUT                                      │
│                         (Cmd + Shift + Space)                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SCREENSHOT CAPTURE                                 │
│              (Captured BEFORE overlay appears for clean image)              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         OVERLAY UI APPEARS                                   │
│                    (Electron transparent overlay)                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ROUTER MODEL                                        │
│                    (gemini-flash-lite-latest)                               │
│                                                                              │
│  Analyzes user request (NO screenshot) and decides routing:                 │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────────┐ ┌──────────────────┐ │
│  │direct_response │ │ invoke_clovis  │ │ invoke_browser │ │invoke_cua_vision │ │
│  │ Simple Q&A     │ │Screen annotate │ │ Web automation │ │GUI-based control │ │
│  └───────┬────────┘ └───────┬────────┘ └───────┬────────┘ └────────┬─────────┘ │
└──────────┼──────────────────┼──────────────────┼───────────────────┼───────────┘
           │                  │                  │                   │
           ▼                  ▼                  ▼                   ▼
┌──────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌───────────────────┐
│  DIRECT RESPONSE │ │  CLOVIS AGENT   │ │  BROWSER AGENT  │ │  CUA VISION AGENT │
│                  │ │                 │ │                 │ │                   │
│ Immediate text   │ │ + Screenshot    │ │ Playwright-     │ │ + Screenshot      │
│ response in      │ │ + Vision model  │ │ based web       │ │ + Element finding │
│ overlay bubble   │ │ + Draw boxes,   │ │ automation      │ │ + Mouse clicks    │
│                  │ │   text, pointers│ │                 │ │ + Keyboard input  │
│                  │ │ + Timed         │ │ (Coming Soon)   │ │ + TTS feedback    │
│                  │ │   sequences     │ │                 │ │                   │
└──────────────────┘ └─────────────────┘ └─────────────────┘ └───────────────────┘
```

### Directory Structure

```
CLOVIS/
├── app.py                      # Entry point - starts server and handles input
├── settings.json               # Runtime configuration (port, models, screen size)
│
├── core/                       # Shared utilities
│   ├── settings.py             # Settings management (read/write settings.json)
│   └── registry.py             # Element registry (tracks drawn boxes/text)
│
├── models/                     # LLM integration and routing
│   ├── models.py               # GeminiModel class, call_gemini(), routing logic
│   ├── function_calls.py       # Router tool declarations (invoke_*)
│   └── prompts.py              # Router system prompt
│
├── agents/                     # Execution backends
│   ├── clovis/                 # Screen annotation agent
│   │   ├── agent.py            # ClovisAgent class
│   │   ├── tools.py            # Drawing tools (boxes, text, pointers)
│   │   └── prompts.py          # CLOVIS system prompt
│   │
│   ├── browser/                # Web automation agent (Playwright)
│   │   └── agent.py            # BrowserAgent class (stub)
│   │
│   ├── cua_cli/                # Desktop control via shell commands
│   │   └── agent.py            # CLIAgent class (stub)
│   │
│   └── cua_vision/             # Desktop control via screen + mouse/keyboard
│       ├── agent.py            # VisionAgent class
│       ├── tools.py            # Tool declarations and functions
│       ├── keyboard.py         # Keyboard and mouse input functions
│       ├── image.py            # Image comparison utilities
│       └── prompts.py          # System prompts
│
├── ui/                         # Electron overlay application
│   ├── main.js                 # Electron main process
│   ├── renderer.js             # Canvas rendering logic
│   ├── preload.js              # IPC bridge
│   ├── index.html              # Overlay HTML
│   ├── server.py               # WebSocket server (Python ↔ Electron)
│   │
│   ├── animations/             # UI animations
│   │   ├── command_overlay.js  # Input bar animation
│   │   ├── overlay_image.js    # Background effects
│   │   └── screen_glow.js      # Glow effects
│   │
│   ├── dom_nodes/              # DOM element factories
│   │   ├── overlay_box.js      # Bounding box elements
│   │   └── overlay_text.js     # Text bubble elements
│   │
│   └── visualization_api/      # Python → Electron drawing API
│       ├── client.py           # WebSocket client singleton
│       ├── draw_bounding_box.py
│       ├── draw_dot.py
│       ├── create_text.py
│       ├── destroy_box.py
│       ├── destroy_text.py
│       └── clear_screen.py
│
├── integrations/               # External service integrations
│   ├── audio/                  # TTS/STT via ElevenLabs
│   │   ├── __init__.py         # Exports tts_speak, stop_speaking
│   │   └── tts.py              # Text-to-speech implementation
│   ├── google-drive/           # Cloud storage (planned)
│   └── messaging/              # Slack, Discord, etc. (planned)
│
└── tests/                      # Test files
```

### Data Flow

#### 1. User Triggers CLOVIS (`Cmd + Shift + Space`)

```
main.js (Electron)
    │
    ├── Sends 'capture_screenshot' event via WebSocket
    │       │
    │       ▼
    │   server.py → models.py: store_screenshot()
    │       (PIL ImageGrab captures screen BEFORE overlay)
    │
    └── Sends 'show-overlay-image' to renderer
            │
            ▼
        command_overlay.js shows input UI
```

#### 2. User Submits Query

```
command_overlay.js
    │
    ├── Sends { event: 'overlay_input', text: '...' }
    │       │
    │       ▼
    │   server.py: on_overlay_input callback
    │       │
    │       ▼
    │   models.py: call_gemini(user_prompt)
    │       │
    │       ▼
    │   ┌─────────────────────────────────┐
    │   │         ROUTER MODEL            │
    │   │   (No screenshot - fast)        │
    │   │                                 │
    │   │   Decides: direct_response,     │
    │   │   invoke_clovis, invoke_browser,│
    │   │   invoke_cua_cli, or            │
    │   │   invoke_cua_vision             │
    │   └─────────────────────────────────┘
    │               │
    │               ▼
    │   ┌─────────────────────────────────┐
    │   │    CLOVIS AGENT (if invoked)    │
    │   │   + Stored screenshot           │
    │   │   + Full vision model           │
    │   │   + Returns tool calls:         │
    │   │     draw_bounding_box(),        │
    │   │     create_text(), etc.         │
    │   └─────────────────────────────────┘
    │               │
    │               ▼
    │   ┌─────────────────────────────────┐
    │   │        ACTION QUEUE             │
    │   │   Processes tool calls with     │
    │   │   time delays for animations    │
    │   └─────────────────────────────────┘
    │               │
    │               ▼
    │   visualization_api/client.py
    │       │
    │       ▼
    └── WebSocket to renderer.js
            │
            ▼
        Canvas draws boxes/text/dots
```

### Key Components

#### Router Model (models/function_calls.py)

The router is a lightweight model that classifies requests without seeing the screen:

| Tool | When to Use |
|------|-------------|
| `direct_response` | Simple facts, math, greetings |
| `invoke_clovis` | Screen questions, "what's this?", visual explanation |
| `invoke_browser` | Web tasks, searches, online services |
| `invoke_cua_cli` | Shell commands, file ops, scripts |
| `invoke_cua_vision` | GUI interactions, clicking buttons |

#### CLOVIS Agent (agents/clovis/)

Screen annotation agent with timed visual elements:

| Tool | Description |
|------|-------------|
| `draw_bounding_box` | Rectangle around UI elements |
| `draw_pointer_to_object` | Dot + text + connecting line |
| `create_text` | Text label at coordinates |
| `create_text_for_box` | Text positioned relative to a box |
| `destroy_box` / `destroy_text` | Remove elements by ID |
| `clear_screen` | Remove all annotations |
| `direct_response` | Text in center overlay bubble |

All tools accept a `time` parameter (seconds from start) enabling animated sequences.

#### CUA Vision Agent (agents/cua_vision/)

Vision-based computer use agent that can see and interact with the screen:

| Tool | Description |
|------|-------------|
| `type_string` | Types out a string using the keyboard |
| `click_left_click` | Left click at coordinates |
| `click_double_left_click` | Double click at coordinates |
| `click_right_click` | Right click at coordinates |
| `press_ctrl_hotkey` | Press Ctrl+key (e.g., Ctrl+C) |
| `press_alt_hotkey` | Press Alt+key |
| `find_and_click_element` | Find element by description and click it |
| `remember_information` | Store information in memory |
| `tts_speak` | Speak to user via TTS |

The agent operates in a loop: capture screen → analyze → execute action → repeat until task complete.

#### Action Queue (agents/clovis/tools.py)

The action queue handles timed execution:

```python
ACTION_QUEUE = deque()  # [(time, func, args, kwargs), ...]

# Example sequence:
draw_bounding_box(time=0.0, ...)   # Show immediately
create_text(time=0.5, ...)         # Show after 0.5s
destroy_box(time=3.0, ...)         # Remove after 3s
```

#### WebSocket Communication

```
Python Server (server.py:8765)
        │
        │  JSON messages
        │
        ▼
Electron Renderer (renderer.js)

Commands (Python → Electron):
  { command: "draw_box", id, x, y, width, height, stroke, ... }
  { command: "draw_text", id, x, y, text, color, fontSize, ... }
  { command: "draw_dot", id, x, y, radius, lineToId, ... }
  { command: "remove_box", id }
  { command: "clear" }
  { command: "set_model_name", name }

Events (Electron → Python):
  { event: "viewport", width, height }
  { event: "overlay_input", text }
  { event: "capture_screenshot" }
  { event: "click", id }
```

### Configuration (settings.json)

```json
{
    "host": "127.0.0.1",
    "port": 8765,
    "screen_width": 1920,
    "screen_height": 1080,
    "viewport_width": 1920,
    "viewport_height": 1080,
    "rapid_response_model": "gemini-flash-lite-latest",
    "clovis_model": "gemini-2.5-flash-preview-04-17"
}
```

### Adding a New Agent

1. Create directory: `agents/my_agent/`
2. Create your agent class:
   ```python
   class MyAgent:
       def __init__(self):
           pass

       async def execute(self, task: str) -> dict:
           # Do the work
           return {"success": True, "result": ..., "error": None}
   ```
3. Add routing tool declaration in `models/function_calls.py`:
   ```python
   invoke_my_agent_declaration = {
       "name": "invoke_my_agent",
       "description": "When to use this agent...",
       "parameters": { ... }
   }
   ```
4. Add routing logic in `models/models.py` to handle the new tool
5. Update router prompt in `models/prompts.py` to tell router when to use it
