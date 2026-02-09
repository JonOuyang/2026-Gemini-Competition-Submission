"""
Browser Agent - Web automation via browser-use.

Creates a fresh, headed browser window for each task and runs the browser-use agent.
"""

from __future__ import annotations

import asyncio
import atexit
import os
import sys
import tempfile
import shutil
import re
from pathlib import Path
from urllib.parse import quote_plus
from typing import Any, Optional

_RETAINED_BROWSER_HANDLES: list[dict[str, Any]] = []


def _ensure_browser_use_on_path() -> None:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    browser_use_root = os.path.join(repo_root, "agents", "browser")
    if browser_use_root not in sys.path:
        sys.path.insert(0, browser_use_root)


class BrowserAgent:
    """
    Browser automation agent using browser-use.

    Starts a new, headed browser window per task and executes the agent loop.
    """
    _shared_backend: Optional[str] = None  # "browser_use" | "playwright" | None
    _shared_browser_use_session: Any = None
    _shared_browser_use_user_data_dir: Optional[str] = None
    _shared_playwright: Any = None
    _shared_playwright_browser: Any = None
    _shared_playwright_context: Any = None
    _shared_playwright_page: Any = None
    _shared_playwright_home: Optional[str] = None
    _shared_playwright_headless: bool = False
    _cleanup_registered: bool = False

    def __init__(self, model_name: str):
        self.model_name = model_name
        self._session = None
        self._register_cleanup_hook()

    @classmethod
    def _register_cleanup_hook(cls) -> None:
        if cls._cleanup_registered:
            return
        # Best-effort synchronous cleanup marker. OS process teardown will close
        # any remaining browser processes if async cleanup cannot run here.
        atexit.register(lambda: None)
        cls._cleanup_registered = True

    @classmethod
    async def _close_shared_resources(cls) -> None:
        if cls._shared_backend == "browser_use":
            session = cls._shared_browser_use_session
            if session is not None:
                try:
                    await session.kill()
                except Exception:
                    pass
            if cls._shared_browser_use_user_data_dir:
                try:
                    shutil.rmtree(cls._shared_browser_use_user_data_dir, ignore_errors=True)
                except Exception:
                    pass
            cls._shared_browser_use_session = None
            cls._shared_browser_use_user_data_dir = None

        elif cls._shared_backend == "playwright":
            context = cls._shared_playwright_context
            browser = cls._shared_playwright_browser
            playwright = cls._shared_playwright

            if context is not None:
                try:
                    await context.close()
                except Exception:
                    pass
            if browser is not None:
                try:
                    await browser.close()
                except Exception:
                    pass
            if playwright is not None:
                try:
                    await playwright.stop()
                except Exception:
                    pass
            if cls._shared_playwright_home:
                try:
                    shutil.rmtree(cls._shared_playwright_home, ignore_errors=True)
                except Exception:
                    pass

            cls._shared_playwright = None
            cls._shared_playwright_browser = None
            cls._shared_playwright_context = None
            cls._shared_playwright_page = None
            cls._shared_playwright_home = None
            cls._shared_playwright_headless = False

        cls._shared_backend = None

    async def _get_or_create_browser_use_session(self):
        _ensure_browser_use_on_path()
        from browser_use.browser import BrowserProfile, BrowserSession

        cls = type(self)
        if cls._shared_backend == "playwright":
            raise RuntimeError("Shared browser backend is already Playwright.")

        if cls._shared_browser_use_session is not None:
            # Ensure existing reused session always stays alive across tasks.
            try:
                cls._shared_browser_use_session.browser_profile.keep_alive = True
            except Exception:
                pass
            return cls._shared_browser_use_session

        user_data_dir = tempfile.mkdtemp(prefix="clovis-browser-use-")
        profile = BrowserProfile(
            headless=False,
            user_data_dir=user_data_dir,
            keep_alive=True,
        )
        session = BrowserSession(browser_profile=profile)
        cls._shared_backend = "browser_use"
        cls._shared_browser_use_session = session
        cls._shared_browser_use_user_data_dir = user_data_dir
        print("[Browser Agent] Created persistent browser-use session.")
        return session

    async def _get_or_create_playwright_page(self):
        from playwright.async_api import async_playwright

        cls = type(self)
        if cls._shared_backend == "browser_use":
            await cls._close_shared_resources()

        existing_page = cls._shared_playwright_page
        try:
            if existing_page is not None and not existing_page.is_closed():
                return existing_page, cls._shared_playwright_headless
        except Exception:
            cls._shared_playwright_page = None

        runtime_home = tempfile.mkdtemp(prefix="clovis-playwright-home-")
        launch_env = dict(os.environ)
        launch_env["HOME"] = runtime_home

        playwright = await async_playwright().start()
        browser, used_headless = await self._launch_playwright_browser(playwright, launch_env)
        context = await browser.new_context()
        page = await context.new_page()

        cls._shared_backend = "playwright"
        cls._shared_playwright = playwright
        cls._shared_playwright_browser = browser
        cls._shared_playwright_context = context
        cls._shared_playwright_page = page
        cls._shared_playwright_home = runtime_home
        cls._shared_playwright_headless = used_headless
        print("[Browser Agent] Created persistent Playwright session.")
        return page, used_headless

    async def execute(self, task: str) -> dict[str, Any]:
        # Extract the direct URL from the ORIGINAL task before steering is applied,
        # so the steering preamble text doesn't produce false URL matches.
        original_direct_url = self._extract_direct_url(task)
        cls = type(self)
        # Only apply "stay on existing page" steering when there's already a
        # browser_use session that might have the target page open.  For fresh
        # sessions the LLM needs freedom to navigate to the correct URL on its own.
        # Note: only steer for browser_use sessions — playwright sessions are
        # navigation-only and will be closed below so the agent can use browser_use.
        if cls._shared_backend == "browser_use":
            task = self._steer_task_for_existing_page(task)
        # Keep browser sessions alive for the full process lifetime.
        close_when_done = False

        # Once a backend is chosen, keep using it so all browser actions stay in
        # the same persistent browser session.
        if cls._shared_backend == "browser_use":
            return await self._execute_with_browser_use(task, close_when_done=close_when_done)
        if cls._shared_backend == "playwright":
            return await self._execute_with_playwright(
                task,
                bootstrap_error="",
                close_when_done=close_when_done,
                pre_extracted_url=original_direct_url,
            )

        # Always try browser_use first — it can actually interact with pages.
        # Playwright fallback is a last resort for navigation-only tasks.
        try:
            result = await self._execute_with_browser_use(task, close_when_done=close_when_done)
            return result
        except Exception as exc:
            if not self._should_fallback_to_playwright(exc):
                return {"success": False, "result": None, "error": str(exc)}

            print(f"[Browser Agent][fallback] browser_use unavailable: {exc}")
            try:
                result = await self._execute_with_playwright(
                    task,
                    bootstrap_error=str(exc),
                    close_when_done=close_when_done,
                    pre_extracted_url=original_direct_url,
                )
                return result
            except Exception as fallback_exc:
                return {
                    "success": False,
                    "result": None,
                    "error": (
                        "Browser task failed in both browser_use and Playwright fallback. "
                        f"bootstrap_error={exc}; fallback_error={fallback_exc}"
                    ),
                }

    async def _execute_with_browser_use(self, task: str, close_when_done: bool) -> dict[str, Any]:
        _ensure_browser_use_on_path()
        from browser_use import Agent
        from browser_use.llm.google.chat import ChatGoogle

        session = await self._get_or_create_browser_use_session()
        self._session = session

        llm = ChatGoogle(model=self.model_name, api_key=os.getenv("GEMINI_API_KEY"))
        available_file_paths = self._extract_available_file_paths_from_task(task)
        if available_file_paths:
            print(f"[Browser Agent] available_file_paths: {available_file_paths}")

        agent = Agent(
            task=task,
            llm=llm,
            browser_session=session,
            available_file_paths=available_file_paths,
        )

        try:
            history = await agent.run()
            if close_when_done:
                await type(self)._close_shared_resources()
            else:
                print("[Browser Agent] Reusing persistent browser window for future tasks.")
            return {"success": True, "result": history, "error": None}
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            return {"success": False, "result": None, "error": str(exc)}
        finally:
            self._session = type(self)._shared_browser_use_session

    async def _execute_with_playwright(self, task: str, bootstrap_error: str, close_when_done: bool, pre_extracted_url: str | None = None) -> dict[str, Any]:
        # Use the pre-extracted URL (from original task) if available,
        # to avoid false matches from steering preamble text.
        direct_url = pre_extracted_url if pre_extracted_url is not None else self._extract_direct_url(task)
        avoid_search = self._must_avoid_search(task)
        used_search = False
        page, used_headless = await self._get_or_create_playwright_page()
        action_mode = "direct_navigation"

        if self._is_open_new_tab_task(task):
            context = type(self)._shared_playwright_context
            if context is not None:
                page = await context.new_page()
                type(self)._shared_playwright_page = page
                action_mode = "new_tab"
            else:
                action_mode = "new_tab_current_context_unavailable"

        need_search_fallback = False

        if action_mode.startswith("new_tab"):
            pass
        elif direct_url:
            await page.goto(direct_url, wait_until="domcontentloaded", timeout=30000)
            action_mode = "direct_navigation"
        elif avoid_search:
            relevant_page = await self._select_relevant_existing_page(task, page)
            if relevant_page is not None:
                page = relevant_page
                type(self)._shared_playwright_page = page
                action_mode = "current_tab_context"
            else:
                # No relevant page found; fall through to search
                need_search_fallback = True
        else:
            need_search_fallback = True

        if need_search_fallback:
            used_search = True
            search_query = self._task_to_search_query(task)
            search_url = f"https://duckduckgo.com/?q={quote_plus(search_query)}"
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await self._open_first_duckduckgo_result(page)
            action_mode = "search_fallback"

        await page.wait_for_timeout(1000)
        final_url = page.url
        title = await page.title()

        summary = self._build_fallback_summary(
            task=task,
            final_url=final_url,
            page_title=title,
            used_search=used_search,
            used_headless=used_headless,
            action_mode=action_mode,
        )

        if close_when_done:
            await type(self)._close_shared_resources()
        else:
            print("[Browser Agent] Reusing persistent browser window for future tasks.")

        return {
            "success": True,
            "result": {
                "summary": summary,
                "mode": "playwright_fallback",
                "task": task,
                "url": final_url,
                "title": title,
                "bootstrap_error": bootstrap_error,
            },
            "error": None,
        }

    async def _open_first_duckduckgo_result(self, page) -> None:
        selectors = [
            "a[data-testid='result-title-a']",
            "a.result__a",
        ]
        for selector in selectors:
            try:
                result = page.locator(selector).first
                await result.wait_for(state="visible", timeout=5000)
                await result.click()
                await page.wait_for_load_state("domcontentloaded", timeout=15000)
                return
            except Exception:
                continue

    async def _launch_playwright_browser(self, playwright, launch_env: dict[str, str]):
        launch_args = ["--disable-crashpad", "--disable-crash-reporter"]
        errors: list[str] = []

        for headless in (False, True):
            try:
                browser = await playwright.chromium.launch(
                    headless=headless,
                    env=launch_env,
                    args=launch_args,
                )
                return browser, headless
            except Exception as exc:
                errors.append(f"bundled chromium headless={headless}: {exc}")

        for channel in ("chrome", "msedge"):
            for headless in (False, True):
                try:
                    browser = await playwright.chromium.launch(
                        channel=channel,
                        headless=headless,
                        env=launch_env,
                        args=launch_args,
                    )
                    return browser, headless
                except Exception as exc:
                    errors.append(f"channel {channel} headless={headless}: {exc}")

        for executable_path in self._known_browser_executables():
            for headless in (False, True):
                try:
                    browser = await playwright.chromium.launch(
                        executable_path=executable_path,
                        headless=headless,
                        env=launch_env,
                        args=launch_args,
                    )
                    return browser, headless
                except Exception as exc:
                    errors.append(f"executable {executable_path} headless={headless}: {exc}")

        raise RuntimeError(
            "Could not launch Playwright browser. "
            "Tried bundled Chromium, channels, and local executables. "
            "If needed, run: playwright install. "
            f"Launch errors: {' | '.join(errors[:6])}"
        )

    @staticmethod
    def _known_browser_executables() -> list[str]:
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
        return [path for path in candidates if Path(path).exists()]

    @staticmethod
    def _should_close_after_task(task: str) -> bool:
        lowered = task.lower()

        keep_open_markers = [
            "stay open",
            "keep open",
            "leave open",
            "do not close",
            "don't close",
        ]
        if any(marker in lowered for marker in keep_open_markers):
            return False

        close_markers = [
            "close the browser",
            "close browser",
            "close the window",
            "close window",
            "close the tab",
            "close tab",
            "quit browser",
            "exit browser",
        ]
        return any(marker in lowered for marker in close_markers)

    @staticmethod
    def _should_fallback_to_playwright(exc: Exception) -> bool:
        if isinstance(exc, (ImportError, ModuleNotFoundError)):
            return True
        lowered = str(exc).lower()
        markers = [
            "failed to import",
            "no module named",
            "cannot import name",
            "unsupported operand type(s) for |",
        ]
        return any(marker in lowered for marker in markers)

    @staticmethod
    def _extract_direct_url(task: str) -> str | None:
        task = task.strip()
        if not task:
            return None

        url_match = re.search(r"https?://[^\s]+", task)
        if url_match:
            return url_match.group(0).rstrip(".,);")

        domain_match = re.search(r"\b([a-zA-Z0-9-]+\.(?:com|org|edu|gov|net|io|ai|co))\b", task)
        if domain_match:
            return f"https://{domain_match.group(1)}"

        localhost_match = re.search(
            r"\b(localhost|127\.0\.0\.1)(?:\s*:\s*|\s+)?(\d{2,5})?([/\w\-.?=&%+]*)",
            task,
            flags=re.IGNORECASE,
        )
        if localhost_match:
            host = localhost_match.group(1)
            port = localhost_match.group(2)
            path = (localhost_match.group(3) or "").strip()
            path = path.rstrip(".,);")
            normalized = f"http://{host}"
            if port:
                normalized += f":{port}"
            if path:
                if not path.startswith("/"):
                    path = f"/{path}"
                normalized += path
            return normalized

        return None

    @staticmethod
    def _extract_available_file_paths_from_task(task: str) -> list[str]:
        """Extract likely local file paths from task text for upload whitelisting."""
        if not task:
            return []

        candidates: list[str] = []

        # Quoted chunks commonly contain explicit file paths.
        for quoted in re.findall(r"""['"]([^'"]+)['"]""", task):
            q = quoted.strip()
            if q:
                candidates.append(q)

        # Also capture unquoted absolute/home-relative paths.
        for match in re.findall(r"""(?<!\w)(~\/[^\s,;]+|\/[^\s,;]+)""", task):
            m = str(match).strip()
            if m:
                candidates.append(m)

        resolved: list[str] = []
        seen: set[str] = set()

        def add(path_value: str) -> None:
            p = str(path_value).strip()
            if not p:
                return
            # Trim surrounding punctuation that can appear in prose.
            p = p.strip(".,;:()[]{}'\"`")
            if not p or p in seen:
                return
            seen.add(p)
            resolved.append(p)

        for candidate in candidates:
            # Skip obvious non-path tokens.
            if "/" not in candidate and "\\" not in candidate and "~" not in candidate:
                continue

            expanded = os.path.expandvars(os.path.expanduser(candidate))
            absolute = os.path.abspath(expanded)

            add(expanded)
            add(absolute)
            add(candidate)

            base = os.path.basename(expanded)
            if base:
                add(base)

        return resolved

    @staticmethod
    def _is_open_new_tab_task(task: str) -> bool:
        lowered = task.lower()
        markers = [
            "open a new browser tab",
            "open new browser tab",
            "open a new tab",
            "open new tab",
            "new tab",
        ]
        return any(marker in lowered for marker in markers)

    @staticmethod
    def _is_current_tab_context_task(task: str) -> bool:
        lowered = task.lower()
        markers = [
            "currently open",
            "current tab",
            "already open",
            "on the page",
            "on this page",
            "that is open",
        ]
        return any(marker in lowered for marker in markers)

    @classmethod
    def _should_reuse_existing_page(cls, task: str) -> bool:
        lowered = task.lower()
        if cls._is_current_tab_context_task(task):
            return True
        # Product-specific heuristics to avoid incorrect search fallbacks.
        sticky_site_markers = [
            "scopegrade",
        ]
        return any(marker in lowered for marker in sticky_site_markers)

    @classmethod
    def _steer_task_for_existing_page(cls, task: str) -> str:
        """
        If the user indicates the target page is already open, prepend strict
        instructions to avoid search/navigation drift.
        """
        lowered = task.lower()
        wants_localhost = ("localhost" in lowered) or ("127.0.0.1" in lowered) or ("scopegrade" in lowered)

        if not cls._should_reuse_existing_page(task) and not wants_localhost:
            return task

        if wants_localhost:
            steering = (
                "HARD CONSTRAINT (LOCAL-SITE MODE):\n"
                "- You MUST use the currently open local-server page/tab in this browser session.\n"
                "- Do NOT perform web search.\n"
                "- Do NOT type the full task sentence into the browser address/search bar.\n"
                "- Do NOT navigate to unrelated public websites.\n"
                "- If a navigation is required, only use local-server URLs (e.g. http://127.0.0.1:PORT).\n"
                "- Prioritize interacting with the existing on-page UI to complete the task.\n\n"
                "Task:\n"
            )
            return f"{steering}{task}"

        steering = (
            "IMPORTANT EXECUTION CONSTRAINTS:\n"
            "- The target page is already open in the current browser session.\n"
            "- Stay on the currently open relevant tab/page.\n"
            "- Do NOT perform web search and do NOT navigate to unrelated sites.\n"
            "- Do NOT type the full task sentence into the browser address/search bar.\n"
            "- Only navigate if the task explicitly gives a direct URL.\n"
            "- Prioritize interacting with existing on-page UI to complete the task.\n\n"
            "Task:\n"
        )
        return f"{steering}{task}"

    @classmethod
    def _must_avoid_search(cls, task: str) -> bool:
        lowered = task.lower()
        if cls._should_reuse_existing_page(task):
            return True
        return ("localhost" in lowered) or ("127.0.0.1" in lowered) or ("scopegrade" in lowered)

    async def _select_relevant_existing_page(self, task: str, default_page):
        """Return a matching open page, or None if no relevant page is found."""
        lowered = task.lower()
        context = type(self)._shared_playwright_context
        if context is None:
            return None
        pages = list(getattr(context, "pages", []) or [])
        if not pages:
            return None

        if "scopegrade" in lowered:
            for candidate in pages:
                try:
                    title = (await candidate.title()).lower()
                    url = (candidate.url or "").lower()
                except Exception:
                    continue
                if "scopegrade" in title or "scopegrade" in url:
                    return candidate
                if "localhost" in url or "127.0.0.1" in url:
                    return candidate

        if "localhost" in lowered or "127.0.0.1" in lowered:
            for candidate in pages:
                url = (candidate.url or "").lower()
                if "localhost" in url or "127.0.0.1" in url:
                    return candidate

        return None

    @staticmethod
    def _task_to_search_query(task: str) -> str:
        cleaned = " ".join(task.split())
        if not cleaned:
            return "official website"
        if re.search(r"\b(go to|open|visit)\b", cleaned, flags=re.IGNORECASE):
            return cleaned
        return f"{cleaned} official website"

    @staticmethod
    def _build_fallback_summary(
        task: str,
        final_url: str,
        page_title: str,
        used_search: bool,
        used_headless: bool,
        action_mode: str = "direct_navigation",
    ) -> str:
        if action_mode == "new_tab":
            mode_text = "new-tab action"
        elif action_mode == "current_tab_context":
            mode_text = "current-tab context fallback"
        else:
            mode_text = "search fallback" if used_search else "direct navigation fallback"
        title_text = page_title.strip() if isinstance(page_title, str) else ""
        if used_headless:
            mode_text = f"{mode_text} (headless)"
        if title_text:
            return f"Browser task completed via {mode_text}: {title_text} ({final_url})"
        return f"Browser task completed via {mode_text}: {final_url}"

    async def stop(self):
        await type(self)._close_shared_resources()

        for handle in list(_RETAINED_BROWSER_HANDLES):
            kind = handle.get("kind")
            try:
                if kind == "browser_use":
                    session = handle.get("session")
                    if session is not None:
                        await session.kill()
                elif kind == "playwright":
                    browser = handle.get("browser")
                    playwright = handle.get("playwright")
                    if browser is not None:
                        await browser.close()
                    if playwright is not None:
                        await playwright.stop()
            except Exception:
                pass

            user_data_dir = handle.get("user_data_dir")
            if user_data_dir:
                try:
                    shutil.rmtree(user_data_dir, ignore_errors=True)
                except Exception:
                    pass
            _RETAINED_BROWSER_HANDLES.remove(handle)

        if self._session is None:
            return
        try:
            await self._session.kill()
        finally:
            self._session = None
