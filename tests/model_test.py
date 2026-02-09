import asyncio
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from core.settings import get_model_configs
from models.models import call_gemini


async def run_model_intro_test():
    """Test the two-tier model system."""
    settings_path = os.path.join(os.path.dirname(__file__), "..", "settings.json")
    rapid_response_model, clovis_model = get_model_configs(settings_path)

    print("=== Testing two-tier model system ===")
    print(f"Rapid Response Model: {rapid_response_model}")
    print(f"CLOVIS Model: {clovis_model}\n")

    # Test 1: Query that should use rapid response (no screen needed)
    print("Test 1: 'What is 2+2?' (should use rapid response)")
    await call_gemini("What is 2+2?", rapid_response_model, clovis_model)

    print("\n" + "="*50 + "\n")

    # Test 2: Query that should invoke CLOVIS (needs screen)
    print("Test 2: 'What's on my screen?' (should invoke CLOVIS)")
    await call_gemini("What's on my screen?", rapid_response_model, clovis_model)


if __name__ == "__main__":
    asyncio.run(run_model_intro_test())
