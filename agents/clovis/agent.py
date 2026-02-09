"""
CLOVIS Agent - Screen annotation and visual explanation.

This agent receives a screenshot and user query, then generates
timed annotations (boxes, text, pointers) to explain what's on screen.
"""
from PIL import Image
from agents.clovis.tools import CLOVIS_TOOLS, CLOVIS_TOOL_MAP, set_model_name
from agents.clovis.prompts import CLOVIS_SYSTEM_PROMPT


class ClovisAgent:
    """
    Screen annotation agent that draws visual explanations on the user's screen.

    Capable of:
    - Drawing bounding boxes around UI elements
    - Creating text labels and annotations
    - Drawing pointer dots with connecting lines
    - Timed sequences of annotations for explanations
    - Direct text responses for simple queries
    """

    def __init__(self, model_client, model_name: str, config):
        """
        Initialize the CLOVIS agent.

        Args:
            model_client: The Gemini client instance
            model_name: Name of the model to use (e.g., "gemini-3-flash-preview")
            config: GenerateContentConfig for the model
        """
        self.client = model_client
        self.model_name = model_name
        self.config = config
        self.tools = CLOVIS_TOOLS
        self.tool_map = CLOVIS_TOOL_MAP

    async def execute(self, task: str, screenshot: Image = None) -> dict:
        """
        Execute a screen annotation task.

        Args:
            task: The user's query/request
            screenshot: PIL.Image of the current screen

        Returns:
            dict with keys:
                - success: bool
                - result: The model response
                - error: Optional error message if failed
        """
        try:
            await set_model_name(self.model_name)

            prompt = CLOVIS_SYSTEM_PROMPT + f"\n# User's Request:\n{task}"

            contents = [prompt]
            if screenshot:
                contents.append(screenshot)

            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=self.config
            )

            parts = response.candidates[0].content.parts
            function_calls = [part.function_call for part in parts if part.function_call]

            if function_calls:
                for function_call in function_calls:
                    print(f"\n[CLOVIS] Function: {function_call.name}")
                    print(f"[CLOVIS] Arguments: {function_call.args}")

                    tool = self.tool_map.get(function_call.name)
                    if tool:
                        tool(**function_call.args)
                    else:
                        return {
                            "success": False,
                            "result": None,
                            "error": f"Unknown tool: {function_call.name}"
                        }

            return {
                "success": True,
                "result": response,
                "error": None
            }

        except Exception as e:
            return {
                "success": False,
                "result": None,
                "error": str(e)
            }
