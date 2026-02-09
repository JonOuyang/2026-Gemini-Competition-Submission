"""
Regression checks for CUA vision alternating click-loop detection.

Usage:
    python tests/test_cua_vision_loop_guard.py
"""

import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from agents.cua_vision.single_call import (
    SingleCallVisionEngine,
    CLICK_CYCLE_LOOP_STOP_THRESHOLD,
)


class _DummyAgent:
    client = None
    model_name = "dummy"
    analysis_config = None
    retries = 0
    max_retries = 3


def test_detects_alternating_position_click_loop() -> None:
    engine = SingleCallVisionEngine(_DummyAgent())
    task = "Open Settings and change appearance to Light Mode."

    position_sig = ("go_to_element", ("bucket", 24, 7))
    click_sig = ("click_left_click", (("target_description", "Light mode option"),))

    for _ in range(CLICK_CYCLE_LOOP_STOP_THRESHOLD - 1):
        assert not engine._register_action_and_detect_click_loop(
            task, "go_to_element", position_sig, None
        )
        assert not engine._register_action_and_detect_click_loop(
            task, "click_left_click", click_sig, "left click"
        )

    assert not engine._register_action_and_detect_click_loop(
        task, "go_to_element", position_sig, None
    )
    assert engine._register_action_and_detect_click_loop(
        task, "click_left_click", click_sig, "left click"
    )


def test_allows_intentional_repeat_click_tasks() -> None:
    engine = SingleCallVisionEngine(_DummyAgent())
    task = "Click the plus button 10 times."

    position_sig = ("go_to_element", ("bucket", 11, 15))
    click_sig = ("click_left_click", (("target_description", "plus button"),))

    for _ in range(CLICK_CYCLE_LOOP_STOP_THRESHOLD + 3):
        assert not engine._register_action_and_detect_click_loop(
            task, "go_to_element", position_sig, None
        )
        assert not engine._register_action_and_detect_click_loop(
            task, "click_left_click", click_sig, "left click"
        )


if __name__ == "__main__":
    test_detects_alternating_position_click_loop()
    test_allows_intentional_repeat_click_tasks()
    print("[test_cua_vision_loop_guard] All checks passed.")
