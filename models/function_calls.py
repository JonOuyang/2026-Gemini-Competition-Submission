"""
Router Tools - Rapid response model tool definitions for routing requests.

This module contains the tools available to the rapid response (router) model,
which decides how to handle user requests by delegating to appropriate agents.
"""
from google.genai import types

# Import direct_response from CLOVIS agent (used by both router and CLOVIS)
from agents.clovis.tools import direct_response


# ================================================================================
# ROUTING TOOL DECLARATIONS
# ================================================================================

direct_response_declaration = {
    "name": "direct_response",
    "description": "Respond directly to the user for simple questions that don't require screen access, browser, or desktop control.",
    "parameters": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Response text to render."},
            "font_size": {"type": "integer", "description": "Font size in pixels.", "default": 18},
            "font_family": {"type": "string", "description": "Font family name.", "default": "Helvetica"},
        },
        "required": ["text"],
    },
}

invoke_clovis_declaration = {
    "name": "invoke_clovis",
    "description": "Delegate to CLOVIS for screen annotation and explanation. Use when the user wants to understand something on their screen, needs visual explanation, or refers to 'this', 'that', 'here', etc.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The user's query to pass to CLOVIS."},
        },
        "required": ["query"],
    },
}

invoke_browser_declaration = {
    "name": "invoke_browser",
    "description": "Delegate to the Browser Agent for web automation. Use for tasks involving websites, web searches, online forms, or any browser-based interactions.",
    "parameters": {
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "The browser task to perform. Preserve the user's original wording, context, and any site/URL references faithfully. Do not paraphrase or strip context."},
        },
        "required": ["task"],
    },
}

invoke_cua_cli_declaration = {
    "name": "invoke_cua_cli",
    "description": "Delegate to the CLI Agent for shell-based desktop control. Use for running commands, opening apps via terminal, file operations, and script execution.",
    "parameters": {
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "Description of the CLI task to perform."},
        },
        "required": ["task"],
    },
}

invoke_cua_vision_declaration = {
    "name": "invoke_cua_vision",
    "description": "Delegate to the Vision Agent for GUI-based desktop control. Use for clicking buttons, interacting with visual interfaces, and tasks requiring screen understanding.",
    "parameters": {
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "Description of the vision-based task to perform."},
        },
        "required": ["task"],
    },
}

request_screen_context_declaration = {
    "name": "request_screen_context",
    "description": (
        "Request a one-shot multimodal screen context analysis to inform routing. "
        "Use when the task references visible screen content (e.g., 'this repo', "
        "'that URL', 'on my screen') and you need concrete context before choosing "
        "invoke_cua_cli/invoke_browser/invoke_cua_vision."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "Original user task/request."},
            "focus": {"type": "string", "description": "Optional thing to extract from screen (repo URL, local URL, etc.)."},
        },
        "required": ["task"],
    },
}


# ================================================================================
# PLACEHOLDER FUNCTIONS (actual invocation handled in router)
# ================================================================================

def invoke_clovis(query: str):
    """Marker function - signals that ClovisAgent should be called."""
    pass


def invoke_browser(task: str):
    """Marker function - signals that BrowserAgent should be called."""
    pass


def invoke_cua_cli(task: str):
    """Marker function - signals that CLIAgent should be called."""
    pass


def invoke_cua_vision(task: str):
    """Marker function - signals that VisionAgent should be called."""
    pass


def request_screen_context(task: str, focus: str = ""):
    """Marker function - signals that screen judge context should be collected."""
    pass


# ================================================================================
# ROUTER TOOL SET
# ================================================================================

ROUTER_TOOLS = [types.Tool(function_declarations=[
    direct_response_declaration,
    invoke_clovis_declaration,
    invoke_browser_declaration,
    invoke_cua_cli_declaration,
    invoke_cua_vision_declaration,
    request_screen_context_declaration,
])]

ROUTER_TOOL_MAP = {
    "direct_response": direct_response,
    "invoke_clovis": invoke_clovis,
    "invoke_browser": invoke_browser,
    "invoke_cua_cli": invoke_cua_cli,
    "invoke_cua_vision": invoke_cua_vision,
    "request_screen_context": request_screen_context,
}

# Legacy aliases for backwards compatibility
RAPID_RESPONSE_TOOLS = ROUTER_TOOLS
RAPID_RESPONSE_TOOL_MAP = ROUTER_TOOL_MAP

TOOL_CONFIG = types.ToolConfig(
    function_calling_config=types.FunctionCallingConfig(
        mode="ANY",
    )
)
