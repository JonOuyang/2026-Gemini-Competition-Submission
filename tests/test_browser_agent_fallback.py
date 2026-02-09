"""
Lightweight checks for BrowserAgent fallback helpers.

Usage:
    python tests/test_browser_agent_fallback.py
"""

import asyncio
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from agents.browser.agent import BrowserAgent


class _FakePage:
    def __init__(self, url: str, title_text: str):
        self.url = url
        self._title_text = title_text
        self.goto_calls: list[str] = []

    async def goto(self, url: str, wait_until: str = "domcontentloaded", timeout: int = 30000):
        self.goto_calls.append(url)
        self.url = url

    async def wait_for_timeout(self, ms: int):
        return None

    async def title(self) -> str:
        return self._title_text

    def is_closed(self) -> bool:
        return False


class _FakeContext:
    def __init__(self, pages):
        self.pages = pages

    async def new_page(self):
        page = _FakePage("about:blank", "Blank")
        self.pages.append(page)
        return page


async def _run_backend_reuse_check() -> None:
    agent = BrowserAgent(model_name="test-model")
    cls = BrowserAgent

    original_backend = cls._shared_backend
    original_close = cls._close_shared_resources
    original_execute_browser_use = agent._execute_with_browser_use
    original_execute_playwright = agent._execute_with_playwright

    calls: list[str] = []

    async def _fake_close_shared_resources(inner_cls):
        inner_cls._shared_backend = None

    async def _fake_execute_browser_use(task: str, close_when_done: bool):
        calls.append(f"browser_use:{task}")
        return {"success": True, "result": task, "error": None}

    async def _fake_execute_playwright(task: str, bootstrap_error: str, close_when_done: bool):
        calls.append(f"playwright:{task}")
        return {"success": True, "result": task, "error": None}

    cls._close_shared_resources = classmethod(_fake_close_shared_resources)
    agent._execute_with_browser_use = _fake_execute_browser_use
    agent._execute_with_playwright = _fake_execute_playwright
    try:
        cls._shared_backend = "browser_use"
        result = await agent.execute("task-1")
        assert result["success"]
        assert calls[-1] == "browser_use:task-1", calls

        cls._shared_backend = "playwright"
        result = await agent.execute("task-2")
        assert result["success"]
        assert calls[-1] == "playwright:task-2", calls
    finally:
        cls._shared_backend = original_backend
        cls._close_shared_resources = original_close
        agent._execute_with_browser_use = original_execute_browser_use
        agent._execute_with_playwright = original_execute_playwright


async def _run_no_search_when_reusing_page_check() -> None:
    agent = BrowserAgent(model_name="test-model")
    cls = BrowserAgent

    original_context = cls._shared_playwright_context
    original_page = cls._shared_playwright_page
    original_get_page = agent._get_or_create_playwright_page
    original_open_result = agent._open_first_duckduckgo_result

    page = _FakePage("http://localhost:3000/", "ScopeGrade")
    context = _FakeContext([page])

    async def _fake_get_or_create_playwright_page():
        return page, False

    async def _fail_if_search_used(_page):
        raise AssertionError("Search fallback should not execute for current-page tasks.")

    cls._shared_playwright_context = context
    cls._shared_playwright_page = page
    agent._get_or_create_playwright_page = _fake_get_or_create_playwright_page
    agent._open_first_duckduckgo_result = _fail_if_search_used
    try:
        result = await agent._execute_with_playwright(
            "On the currently open ScopeGrade page, upload ECE_131A_HW5.zip",
            bootstrap_error="",
            close_when_done=False,
        )
        assert result["success"], result
        summary = result["result"]["summary"]
        assert "current-tab context fallback" in summary.lower(), summary
        assert not any("duckduckgo.com" in url for url in page.goto_calls), page.goto_calls
    finally:
        cls._shared_playwright_context = original_context
        cls._shared_playwright_page = original_page
        agent._get_or_create_playwright_page = original_get_page
        agent._open_first_duckduckgo_result = original_open_result


def run_checks() -> None:
    assert BrowserAgent._extract_direct_url("Go to https://slac.stanford.edu please") == "https://slac.stanford.edu"
    assert BrowserAgent._extract_direct_url("open stanford.edu") == "https://stanford.edu"
    assert BrowserAgent._extract_direct_url("open localhost 3000") == "http://localhost:3000"
    assert BrowserAgent._extract_direct_url("open localhost:3000") == "http://localhost:3000"
    assert BrowserAgent._extract_direct_url("search for Stanford SLAC website") is None

    assert BrowserAgent._should_fallback_to_playwright(ModuleNotFoundError("No module named 'x'"))
    assert BrowserAgent._should_fallback_to_playwright(ImportError("Failed to import BrowserSession"))
    assert not BrowserAgent._should_fallback_to_playwright(RuntimeError("Task execution failed after startup"))

    q1 = BrowserAgent._task_to_search_query("Go to the Stanford SLAC website")
    q2 = BrowserAgent._task_to_search_query("Stanford Linear Accelerator Center")
    assert "Go to the Stanford SLAC website" == q1
    assert q2.endswith("official website")

    executables = BrowserAgent._known_browser_executables()
    assert isinstance(executables, list)

    assert not BrowserAgent._should_close_after_task("Open YouTube in the browser")
    assert BrowserAgent._should_close_after_task("Open YouTube and then close browser")
    assert not BrowserAgent._should_close_after_task("Open YouTube and keep open")
    assert BrowserAgent._is_open_new_tab_task("Open a new browser tab")
    assert BrowserAgent._is_current_tab_context_task("On the page that is currently open, upload this file")
    assert BrowserAgent._should_reuse_existing_page("Navigate to the ScopeGrade submission page and upload file")
    assert BrowserAgent._must_avoid_search("On the currently open page, upload this file")
    assert BrowserAgent._must_avoid_search("Open localhost 3000")
    assert not BrowserAgent._must_avoid_search("Open youtube.com")
    steered = BrowserAgent._steer_task_for_existing_page(
        "On the currently open ScopeGrade page, upload ECE_131A_HW5.zip"
    )
    assert "do not perform web search" in steered.lower()
    assert "currently open localhost page" in steered.lower()
    assert "temporary hard constraint" in steered.lower()
    assert "do not type the full task sentence" in steered.lower()
    plain = BrowserAgent._steer_task_for_existing_page("Open youtube.com")
    assert plain == "Open youtube.com"

    asyncio.run(_run_backend_reuse_check())
    asyncio.run(_run_no_search_when_reusing_page_check())


if __name__ == "__main__":
    run_checks()
    print("[test_browser_agent_fallback] All checks passed.")
