"""
CLI Agent - Desktop control via Gemini CLI.

Wraps the gemini-cli (TypeScript) to provide shell-based computer control.
The rapid response model invokes this agent for CLI tasks.
"""
import atexit
import asyncio
import json
import os
import tempfile
import re
import signal
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Callable, Awaitable, Any

from dotenv import load_dotenv

# Load environment variables (ensures GEMINI_API_KEY is available)
load_dotenv()


@dataclass
class CLIResponse:
    """Structured response from the CLI agent."""
    success: bool
    output: str
    error: Optional[str] = None
    tool_calls: Optional[List[Dict]] = None


def _clean_join_text(*parts: Any) -> str:
    cleaned_parts: List[str] = []
    for part in parts:
        text = " ".join(str(part or "").split())
        if text:
            cleaned_parts.append(text)
    return " | ".join(cleaned_parts)


class CLIAgent:
    """
    Desktop control agent using Gemini CLI.

    Capable of:
    - Running shell commands
    - Opening applications
    - File system operations
    - Script execution
    - Process management

    The agent wraps the gemini-cli (Node.js) and communicates via subprocess.
    """
    _cleanup_hook_registered = False
    _managed_background_processes: Dict[str, Dict[str, Any]] = {}

    def __init__(
        self,
        gemini_cli_path: Optional[str] = None,
        approval_mode: str = "yolo",
        output_format: str = "stream-json",
        model: Optional[str] = None,
    ):
        """
        Initialize the CLI agent.

        Args:
            gemini_cli_path: Path to gemini-cli directory. Defaults to ./gemini-cli
            approval_mode: Tool approval mode (yolo, auto_edit, default, plan)
            output_format: Output format (text, json, stream-json)
            model: Optional model override
        """
        if gemini_cli_path is None:
            # Default to gemini-cli in the same directory as this agent
            gemini_cli_path = str(Path(__file__).parent / "gemini-cli")

        self.gemini_cli_path = gemini_cli_path
        self.cli_bin = os.path.join(gemini_cli_path, "bundle", "gemini.js")
        self.approval_mode = approval_mode
        self.output_format = output_format
        self.model = model
        self._workspace_dirs = self._compute_workspace_dirs()
        self._gemini_cli_home = self._ensure_gemini_cli_home()
        self._trusted_folders_path = self._ensure_trusted_folders_config()
        self._ensure_cleanup_hook_registered()

        # Check if CLI is built
        self._check_cli_built()

    def _check_cli_built(self) -> None:
        """Check if the gemini-cli has been built."""
        if not os.path.exists(self.cli_bin):
            raise RuntimeError(
                f"Gemini CLI not built. Run 'npm install && npm run build' in {self.gemini_cli_path}"
            )

    def _build_command(self, task: str) -> list[str]:
        """Build the command to execute the CLI."""
        cmd = [
            "node",
            self.cli_bin,
            "--prompt", task,
            "--output-format", self.output_format,
            "--approval-mode", self.approval_mode,
        ]

        for include_dir in self._workspace_dirs:
            cmd.extend(["--include-directories", include_dir])

        if self.model:
            cmd.extend(["--model", self.model])

        return cmd

    def _build_cli_env(self) -> Dict[str, str]:
        env = os.environ.copy()
        if not env.get("GEMINI_API_KEY"):
            raise RuntimeError(
                "GEMINI_API_KEY not found in environment. "
                "Please set it in your .env file."
            )
        # Enable permissive policy for CLOVIS CLI sessions:
        # allow all tools by default while still blocking dangerous shell commands.
        env["CLOVIS_CLI_PERMISSIVE_POLICY"] = "1"
        # Trust this workspace so Gemini CLI does not downgrade approval mode.
        env["GEMINI_CLI_TRUSTED_FOLDERS_PATH"] = self._trusted_folders_path
        # Use a writable Gemini CLI home directory for sessions/tmp storage.
        env["GEMINI_CLI_HOME"] = self._gemini_cli_home
        # Disable sandbox for maximum tool/file access in CLOVIS CLI sessions.
        env["GEMINI_SANDBOX"] = "false"
        return env

    @classmethod
    def _ensure_cleanup_hook_registered(cls) -> None:
        if cls._cleanup_hook_registered:
            return
        atexit.register(cls._cleanup_background_processes_sync)
        cls._cleanup_hook_registered = True

    def _ensure_trusted_folders_config(self) -> str:
        """
        Create a local trustedFolders.json for non-interactive CLI runs.

        Gemini CLI downgrades approval mode to default in untrusted folders.
        This file marks our working directories as TRUST_FOLDER so YOLO can apply.
        """
        trusted_file = Path(tempfile.gettempdir()) / "clovis_gemini_trusted_folders.json"
        entries = {
            str(Path(self.gemini_cli_path).resolve()): "TRUST_FOLDER",
            str(Path(self.gemini_cli_path).resolve().parent.parent.parent): "TRUST_FOLDER",
            str(Path.cwd().resolve()): "TRUST_FOLDER",
            str(Path.home().resolve()): "TRUST_FOLDER",
        }
        trusted_file.write_text(json.dumps(entries, indent=2), encoding="utf-8")
        return str(trusted_file)

    def _ensure_gemini_cli_home(self) -> str:
        """
        Ensure a writable Gemini CLI home directory.
        """
        gemini_home = Path(self.gemini_cli_path).resolve() / ".clovis_gemini_home"
        gemini_home.mkdir(parents=True, exist_ok=True)
        return str(gemini_home)

    @staticmethod
    def _compute_workspace_dirs() -> List[str]:
        """
        Include common directories so workspace-scoped tools (ls/glob/read/write)
        can operate beyond the gemini-cli subfolder.
        """
        paths = [
            str(Path.cwd().resolve()),
            str(Path.home().resolve()),
            str((Path.home() / "Desktop").resolve()),
            "/tmp",
        ]
        deduped: List[str] = []
        for p in paths:
            if p not in deduped and Path(p).exists():
                deduped.append(p)
        return deduped

    @staticmethod
    def _prepare_cli_task(task: str) -> str:
        """
        Add execution guidance so the CLI model performs actions rather than
        only describing commands.
        """
        instruction = (
            "You are running inside CLOVIS with tool access enabled. "
            "Execute the request directly using tools/shell commands instead of giving manual instructions. "
            "Do not claim you cannot access the system. "
            "If a command is blocked by policy or fails, report the exact command and exact error. "
            "For long-running local servers, never run foreground. "
            "Launch detached with nohup/background so it stays alive after this turn, "
            "then verify localhost/port reachability before claiming success."
        )
        return f"{instruction}\n\nTask:\n{task}"

    @staticmethod
    def _prepare_retry_task(task: str) -> str:
        instruction = (
            "Your previous response incorrectly refused execution. "
            "You MUST execute the task now using tools (run_shell_command, file tools, etc.). "
            "Do not provide a 'run this in terminal' suggestion. "
            "Return what you executed and outcome."
        )
        return f"{instruction}\n\nTask:\n{task}"

    @staticmethod
    def _extract_explicit_shell_command(task: str) -> Optional[str]:
        if not task:
            return None

        backtick = re.search(r"`([^`]+)`", task, flags=re.DOTALL)
        if backtick:
            command = backtick.group(1).strip()
            return command if command else None

        prefixed = re.search(r"(?:^|\n)\s*command\s*:\s*(.+)$", task, flags=re.IGNORECASE | re.MULTILINE)
        if prefixed:
            command = prefixed.group(1).strip()
            return command if command else None

        run_line = re.match(r"^\s*(?:run|start|launch)\s+(.+)$", task.strip(), flags=re.IGNORECASE)
        if run_line:
            candidate = run_line.group(1).strip()
            if any(token in candidate for token in ("npm ", "pnpm ", "yarn ", "python", "uvicorn", "node ", "flask")):
                return candidate

        return None

    @staticmethod
    def _is_server_like_command(command: str) -> bool:
        c = command.lower()
        patterns = [
            r"\bnpm\s+run\s+(dev|start|serve)\b",
            r"\bnpm\s+(start|serve)\b",
            r"\bpnpm\s+(dev|start|serve)\b",
            r"\byarn\s+(dev|start|serve)\b",
            r"\bnext\s+dev\b",
            r"\bvite\b",
            r"\bwebpack-dev-server\b",
            r"\buvicorn\b",
            r"\bflask\s+run\b",
            r"\bpython(?:3)?\s+-m\s+http\.server\b",
            r"\bnode\s+.+\b(server|dev)\b",
            r"\bgunicorn\b",
        ]
        return any(re.search(p, c) for p in patterns)

    @classmethod
    def _is_background_intent_task(cls, task: str, command: str) -> bool:
        text = (task or "").lower()
        intent_markers = [
            "localhost",
            "port ",
            "dev server",
            "web server",
            "api server",
            "keep running",
            "background",
            "until i stop",
        ]
        return cls._is_server_like_command(command) or any(marker in text for marker in intent_markers)

    @classmethod
    def _is_server_intent_text(cls, text: str) -> bool:
        lowered = (text or "").lower()
        if not lowered:
            return False
        markers = [
            "localhost",
            "127.0.0.1",
            "local server",
            "dev server",
            "web server",
            "api server",
            "npm start",
            "npm run dev",
            "pnpm dev",
            "yarn dev",
            "uvicorn",
            "flask run",
        ]
        if any(marker in lowered for marker in markers):
            return True
        return cls._is_server_like_command(lowered)

    @classmethod
    def _is_quick_server_launch_task(cls, text: str) -> bool:
        """
        True only when the request is primarily "start/run existing local server".
        False for multi-step setup tasks (clone/install/build/etc.) that need longer runtime.
        """
        lowered = (text or "").lower()
        if not lowered:
            return False

        setup_markers = [
            "clone",
            "git ",
            "install",
            "dependency",
            "dependencies",
            "setup",
            "set up",
            "bootstrap",
            "scaffold",
            "build",
            "compile",
            "create",
            "download",
            "npm ci",
            "pip install",
            "pnpm install",
            "yarn install",
        ]
        if any(marker in lowered for marker in setup_markers):
            return False

        return cls._is_server_intent_text(lowered)

    @staticmethod
    def _extract_port_candidates(text: str) -> List[int]:
        ports = set()
        for m in re.finditer(r"(?:localhost|127\.0\.0\.1)\s*:\s*(\d{2,5})", text, flags=re.IGNORECASE):
            ports.add(int(m.group(1)))
        for m in re.finditer(r"\bport\s+(\d{2,5})\b", text, flags=re.IGNORECASE):
            ports.add(int(m.group(1)))
        for m in re.finditer(r"--port(?:=|\s+)(\d{2,5})", text, flags=re.IGNORECASE):
            ports.add(int(m.group(1)))
        return sorted(p for p in ports if 1 <= p <= 65535)

    @staticmethod
    def _resolve_shell_path(path_expr: str, base_dir: Path) -> Path:
        expanded = os.path.expandvars(os.path.expanduser(path_expr.strip().strip("'\"")))
        candidate = Path(expanded)
        if candidate.is_absolute():
            return candidate.resolve()
        return (base_dir / candidate).resolve()

    @classmethod
    def _extract_server_subcommand(cls, command: str) -> str:
        segments = [segment.strip() for segment in re.split(r"\s*&&\s*", command) if segment.strip()]
        for segment in reversed(segments):
            if cls._is_server_like_command(segment):
                return segment
        return command.strip()

    @staticmethod
    def _extract_shell_command_from_tool_call(tool_call: Dict[str, Any]) -> Optional[str]:
        if not isinstance(tool_call, dict):
            return None
        tool_name = str(tool_call.get("tool_name") or "").strip().lower()
        if tool_name not in {"run_shell_command", "shell", "bash"}:
            return None
        params = tool_call.get("parameters")
        if not isinstance(params, dict):
            return None
        raw = params.get("command") or params.get("cmd") or params.get("script")
        if raw is None:
            return None
        command = str(raw).strip()
        return command or None

    @classmethod
    def _infer_server_launch_from_tool_calls(
        cls,
        tool_calls: Optional[List[Dict[str, Any]]],
    ) -> Optional[Dict[str, str]]:
        if not tool_calls:
            return None

        current_dir = Path.cwd().resolve()
        candidate: Optional[Dict[str, str]] = None

        for tool_call in tool_calls:
            if not isinstance(tool_call, dict):
                continue
            if tool_call.get("status") == "error":
                continue

            command = cls._extract_shell_command_from_tool_call(tool_call)
            if not command:
                continue

            cd_chain = re.match(r"^\s*cd\s+([^;&|]+?)\s*&&\s*(.+)$", command, flags=re.IGNORECASE | re.DOTALL)
            if cd_chain:
                cd_target = cd_chain.group(1).strip()
                remaining = cd_chain.group(2).strip()
                try:
                    current_dir = cls._resolve_shell_path(cd_target, current_dir)
                except Exception:
                    pass
                if cls._is_server_like_command(remaining):
                    candidate = {
                        "command": cls._extract_server_subcommand(remaining),
                        "cwd": str(current_dir),
                    }
                continue

            cd_only = re.match(r"^\s*cd\s+(.+?)\s*$", command, flags=re.IGNORECASE | re.DOTALL)
            if cd_only:
                try:
                    current_dir = cls._resolve_shell_path(cd_only.group(1), current_dir)
                except Exception:
                    pass
                continue

            if cls._is_server_like_command(command):
                candidate = {
                    "command": cls._extract_server_subcommand(command),
                    "cwd": str(current_dir),
                }

        return candidate

    @staticmethod
    async def _is_local_port_open(port: int) -> bool:
        try:
            reader, writer = await asyncio.wait_for(asyncio.open_connection("127.0.0.1", port), timeout=0.6)
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            return False

    @classmethod
    async def _wait_for_any_port(cls, ports: List[int], timeout_seconds: float = 8.0) -> Optional[int]:
        if not ports:
            return None
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            for port in ports:
                if await cls._is_local_port_open(port):
                    return port
            await asyncio.sleep(0.35)
        return None

    @classmethod
    async def _start_background_process(
        cls,
        command: str,
        env: Dict[str, str],
        working_dir: str,
        task: str,
    ) -> dict:
        process_id = uuid.uuid4().hex[:8]
        log_path = os.path.join(tempfile.gettempdir(), f"clovis_cli_bg_{process_id}.log")
        log_file = open(log_path, "ab")
        process = await asyncio.create_subprocess_exec(
            "/bin/zsh",
            "-lc",
            command,
            cwd=working_dir,
            env=env,
            stdout=log_file,
            stderr=log_file,
            start_new_session=True,
        )
        log_file.close()

        pid = process.pid
        try:
            pgid = os.getpgid(pid)
        except Exception:
            pgid = pid

        metadata: Dict[str, Any] = {
            "id": process_id,
            "pid": pid,
            "pgid": pgid,
            "command": command,
            "cwd": working_dir,
            "log_path": log_path,
            "started_at": time.time(),
            "task": task,
        }

        ports = cls._extract_port_candidates(task + "\n" + command)
        if ports:
            metadata["ports"] = ports
            opened = await cls._wait_for_any_port(ports, timeout_seconds=20.0)
            if opened is not None:
                metadata["active_port"] = opened
            else:
                metadata["health_warning"] = f"Started process {pid}, but no expected port became reachable: {ports}"

        cls._managed_background_processes[process_id] = metadata

        summary_parts = [
            f"Started background process {process_id}",
            f"(pid {pid})",
            f"command: {command}",
            f"log: {log_path}",
        ]
        if metadata.get("active_port"):
            summary_parts.append(f"verified on http://127.0.0.1:{metadata['active_port']}")
        elif metadata.get("ports"):
            summary_parts.append(f"expected ports: {metadata['ports']}")
            summary_parts.append("health-check did not confirm readiness yet")

        return {
            "success": True,
            "result": " | ".join(summary_parts),
            "error": None,
            "tool_calls": [{
                "tool_name": "background_process_manager",
                "tool_id": process_id,
                "parameters": {"command": command, "pid": pid, "log_path": log_path},
            }],
        }

    @classmethod
    def _cleanup_background_processes_sync(cls) -> None:
        for proc_id in list(cls._managed_background_processes.keys()):
            meta = cls._managed_background_processes.get(proc_id) or {}
            pgid = int(meta.get("pgid") or 0)
            pid = int(meta.get("pid") or 0)
            try:
                if pgid > 0:
                    os.killpg(pgid, signal.SIGTERM)
                elif pid > 0:
                    os.kill(pid, signal.SIGTERM)
            except Exception:
                pass
            cls._managed_background_processes.pop(proc_id, None)

    @classmethod
    async def stop_background_process(cls, process_id: str) -> bool:
        meta = cls._managed_background_processes.get(process_id)
        if not meta:
            return False
        pgid = int(meta.get("pgid") or 0)
        pid = int(meta.get("pid") or 0)
        try:
            if pgid > 0:
                os.killpg(pgid, signal.SIGTERM)
            elif pid > 0:
                os.kill(pid, signal.SIGTERM)
        except Exception:
            pass
        cls._managed_background_processes.pop(process_id, None)
        return True

    @classmethod
    async def stop_all_background_processes(cls) -> int:
        ids = list(cls._managed_background_processes.keys())
        stopped = 0
        for proc_id in ids:
            if await cls.stop_background_process(proc_id):
                stopped += 1
        return stopped

    @classmethod
    def list_background_processes(cls) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        now = time.time()
        for proc_id, meta in cls._managed_background_processes.items():
            row = {
                "id": proc_id,
                "pid": meta.get("pid"),
                "command": meta.get("command"),
                "log_path": meta.get("log_path"),
                "uptime_seconds": int(max(0, now - float(meta.get("started_at", now)))),
            }
            if meta.get("active_port"):
                row["active_port"] = meta["active_port"]
            rows.append(row)
        return rows

    async def _maybe_handle_background_management_task(self, task: str) -> Optional[dict]:
        lower = task.strip().lower()
        if "list background process" in lower or "show background process" in lower:
            rows = self.list_background_processes()
            if not rows:
                return {"success": True, "result": "No managed background processes.", "error": None}
            lines = [
                f"{row['id']} pid={row['pid']} port={row.get('active_port','-')} uptime={row['uptime_seconds']}s cmd={row['command']}"
                for row in rows
            ]
            return {"success": True, "result": "Managed background processes:\n" + "\n".join(lines), "error": None}

        if "stop all background process" in lower or "kill all background process" in lower:
            count = await self.stop_all_background_processes()
            return {"success": True, "result": f"Stopped {count} background process(es).", "error": None}

        m = re.search(r"(?:stop|kill)\s+background\s+process\s+([a-zA-Z0-9_-]+)", task, flags=re.IGNORECASE)
        if m:
            proc_id = m.group(1).strip()
            ok = await self.stop_background_process(proc_id)
            if ok:
                return {"success": True, "result": f"Stopped background process {proc_id}.", "error": None}
            return {"success": False, "result": None, "error": f"No background process found: {proc_id}"}

        return None

    async def _validate_local_server_claim(self, output_text: str) -> Optional[str]:
        if not output_text:
            return None
        lowered = output_text.lower()
        has_localhost_hint = ("localhost" in lowered) or ("127.0.0.1" in lowered) or ("port " in lowered)
        has_running_hint = any(word in lowered for word in ("running", "started", "listening", "serving", "available at"))
        if not (has_localhost_hint and has_running_hint):
            return None

        ports = self._extract_port_candidates(output_text)
        if not ports:
            return None
        opened = await self._wait_for_any_port(ports, timeout_seconds=15.0)
        if opened is not None:
            return None
        return (
            "Task reported a local server as running, but none of the claimed ports are reachable: "
            f"{ports}. The process likely exited or never started successfully."
        )

    async def _maybe_promote_server_launch_from_tool_calls(
        self,
        task: str,
        response: CLIResponse,
    ) -> Optional[dict]:
        launch = self._infer_server_launch_from_tool_calls(response.tool_calls)
        if not launch:
            return None

        launch_command = launch["command"]
        launch_cwd = launch["cwd"]

        combined = "\n".join(filter(None, [task, response.output, launch_command]))
        ports = self._extract_port_candidates(combined)
        if ports:
            opened = await self._wait_for_any_port(ports, timeout_seconds=1.2)
            if opened is not None:
                # Server already reachable from host. If prior run timed out, treat as
                # success so orchestration can continue.
                if self._is_timeout_error_text(response.error):
                    return {
                        "success": True,
                        "result": _clean_join_text(
                            response.output,
                            f"Local server is reachable on http://127.0.0.1:{opened}.",
                        ),
                        "error": None,
                        "tool_calls": response.tool_calls,
                    }
                return None

        env = self._build_cli_env()
        started = await self._start_background_process(
            command=launch_command,
            env=env,
            working_dir=launch_cwd,
            task=task,
        )

        merged_result = _clean_join_text(response.output, started.get("result"))
        merged_tool_calls: List[Dict[str, Any]] = []
        if response.tool_calls:
            merged_tool_calls.extend(response.tool_calls)
        if started.get("tool_calls"):
            merged_tool_calls.extend(started["tool_calls"])

        return {
            "success": True,
            "result": merged_result,
            "error": None,
            "tool_calls": merged_tool_calls or None,
        }

    @staticmethod
    def _is_timeout_error_text(text: Optional[str]) -> bool:
        lowered = str(text or "").lower()
        return "timed out" in lowered or "timeout" in lowered

    @staticmethod
    def _looks_like_execution_refusal(text: str) -> bool:
        if not text:
            return False
        lowered = text.lower()
        patterns = [
            r"\bi (?:am|do not have|don't have).{0,30}\b(?:ability|access|permission)\b",
            r"\bi cannot\b.{0,40}\b(?:run|execute|create|move|delete|modify)\b",
            r"\bi can (?:however )?provide (?:you )?with (?:the )?commands\b",
            r"\brun (?:the|this) command in your terminal\b",
            r"\bi(?:'m| am) unable to execute shell commands\b",
        ]
        return any(re.search(p, lowered) for p in patterns)

    async def execute(
        self,
        task: str,
        timeout: int = 300,
        status_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> dict:
        """
        Execute a CLI task.

        Args:
            task: The task description for the CLI agent
            timeout: Maximum execution time in seconds
            status_callback: Optional async callback for live status updates

        Returns:
            dict with keys: success, result, error, raw_output
        """
        try:
            management_response = await self._maybe_handle_background_management_task(task)
            if management_response is not None:
                return management_response

            explicit_command = self._extract_explicit_shell_command(task)
            if explicit_command and self._is_background_intent_task(task, explicit_command):
                env = self._build_cli_env()
                return await self._start_background_process(
                    command=explicit_command,
                    env=env,
                    working_dir=str(Path.cwd().resolve()),
                    task=task,
                )

            run_timeout = timeout
            short_timeout_applied = False
            if self._is_quick_server_launch_task(task):
                # Keep server-launch turns snappy so long-running foreground processes
                # are promoted to background quickly.
                run_timeout = min(run_timeout, 3)
                short_timeout_applied = run_timeout < timeout

            prepared_task = self._prepare_cli_task(task)
            response = await self._run_cli(
                prepared_task,
                run_timeout,
                status_callback=status_callback,
            )
            if (
                short_timeout_applied
                and self._is_timeout_error_text(response.error)
                and not response.tool_calls
            ):
                # Short timeout fired before any tool execution. Retry once with full
                # timeout so setup-heavy tasks (clone/install/start) can proceed.
                response = await self._run_cli(
                    prepared_task,
                    timeout,
                    status_callback=status_callback,
                )
            if (
                response.success
                and not response.tool_calls
                and self._looks_like_execution_refusal(response.output)
            ):
                # Retry once with stronger execution-only instructions.
                retry_task = self._prepare_retry_task(task)
                response = await self._run_cli(
                    retry_task,
                    run_timeout,
                    status_callback=status_callback,
                )
            # If CLI used a server-like launch command in tool calls, auto-persist it.
            # This avoids "it said localhost is up, but the process already exited".
            if response.tool_calls:
                promoted = await self._maybe_promote_server_launch_from_tool_calls(task, response)
                if promoted is not None:
                    return promoted
            localhost_claim_error = await self._validate_local_server_claim(response.output)
            if localhost_claim_error:
                # Last chance: if tool traces exist, try one more promotion pass
                # before failing the chain on localhost reachability.
                if response.tool_calls:
                    promoted = await self._maybe_promote_server_launch_from_tool_calls(task, response)
                    if promoted is not None:
                        return promoted
                return {
                    "success": False,
                    "result": response.output,
                    "error": localhost_claim_error,
                    "tool_calls": response.tool_calls,
                }
            return {
                "success": response.success,
                "result": response.output,
                "error": response.error,
                "tool_calls": response.tool_calls,
            }
        except asyncio.TimeoutError:
            return {
                "success": False,
                "result": None,
                "error": f"CLI task timed out after {timeout} seconds",
            }
        except Exception as e:
            return {
                "success": False,
                "result": None,
                "error": str(e),
            }

    @staticmethod
    def _safe_preview(value: object, max_len: int = 80) -> str:
        if value is None:
            return ""
        text = " ".join(str(value).split())
        if len(text) > max_len:
            return f"{text[:max_len - 3]}..."
        return text

    @classmethod
    def _format_tool_status(cls, tool_name: str, parameters: dict) -> str:
        name = (tool_name or "tool").strip()
        friendly = name.replace("_", " ")

        if name in {"run_shell_command", "shell", "bash"}:
            command = cls._safe_preview(
                parameters.get("command")
                or parameters.get("cmd")
                or parameters.get("script"),
                72,
            )
            if command:
                return f"Running command: {command}"
            return "Running shell command..."

        if name in {"read_file", "read_many_files"}:
            path = cls._safe_preview(parameters.get("file_path") or parameters.get("path"))
            if path:
                return f"Reading file: {path}"
            return "Reading files..."

        if name in {"write_file", "edit"}:
            path = cls._safe_preview(parameters.get("file_path") or parameters.get("path"))
            if path:
                return f"Updating file: {path}"
            return "Updating files..."

        if name in {"ls", "glob", "grep", "ripgrep"}:
            path = cls._safe_preview(parameters.get("path") or parameters.get("query"))
            if path:
                return f"{friendly.title()}: {path}"
            return f"{friendly.title()}..."

        return f"Using {friendly}..."

    @classmethod
    def _status_from_stream_event(
        cls,
        event: dict,
        tool_by_id: Dict[str, str],
    ) -> Optional[str]:
        event_type = event.get("type")
        if not event_type:
            return None

        if event_type == "init":
            return "CLI session started..."

        if event_type == "tool_use":
            tool_name = str(event.get("tool_name") or "tool")
            tool_id = event.get("tool_id")
            if isinstance(tool_id, str) and tool_id:
                tool_by_id[tool_id] = tool_name
            params = event.get("parameters")
            if not isinstance(params, dict):
                params = {}
            return cls._format_tool_status(tool_name, params)

        if event_type == "tool_result":
            tool_id = event.get("tool_id")
            tool_name = tool_by_id.get(str(tool_id), "tool")
            if event.get("status") == "error":
                err = event.get("error")
                if isinstance(err, dict):
                    err_msg = cls._safe_preview(err.get("message"), 72)
                else:
                    err_msg = cls._safe_preview(err, 72)
                if err_msg:
                    return f"{tool_name.replace('_', ' ').title()} failed: {err_msg}"
                return f"{tool_name.replace('_', ' ').title()} failed."
            return f"Finished {tool_name.replace('_', ' ')}."

        if event_type == "error":
            msg = cls._safe_preview(event.get("message"), 96)
            if msg:
                return f"CLI error: {msg}"
            return "CLI error."

        if event_type == "result":
            if event.get("status") == "success":
                return "Finalizing CLI response..."
            err = event.get("error")
            if isinstance(err, dict):
                err_msg = cls._safe_preview(err.get("message"), 80)
            else:
                err_msg = cls._safe_preview(err, 80)
            if err_msg:
                return f"CLI task failed: {err_msg}"
            return "CLI task failed."

        return None

    async def _emit_status(
        self,
        status_callback: Optional[Callable[[str], Awaitable[None]]],
        text: Optional[str],
    ) -> None:
        if not status_callback or not text:
            return
        try:
            await status_callback(text)
        except Exception:
            # UI status updates should never break CLI execution.
            pass

    async def _run_cli(
        self,
        task: str,
        timeout: int,
        status_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> CLIResponse:
        """
        Run the gemini-cli with the given task.

        Returns structured response parsed from JSON output.
        """
        cmd = self._build_command(task)

        env = self._build_cli_env()

        # Run the CLI process
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(Path.cwd().resolve()),
            env=env,
        )

        stdout_lines: List[str] = []
        stderr_lines: List[str] = []
        tool_by_id: Dict[str, str] = {}

        async def _read_stdout() -> None:
            if process.stdout is None:
                return
            while True:
                raw = await process.stdout.readline()
                if not raw:
                    break
                line = raw.decode("utf-8", errors="replace").rstrip("\n")
                stdout_lines.append(line)
                if not status_callback:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                status_text = self._status_from_stream_event(event, tool_by_id)
                await self._emit_status(status_callback, status_text)

        async def _read_stderr() -> None:
            if process.stderr is None:
                return
            while True:
                raw = await process.stderr.readline()
                if not raw:
                    break
                stderr_lines.append(raw.decode("utf-8", errors="replace"))

        timed_out = False
        stdout_task = asyncio.create_task(_read_stdout())
        stderr_task = asyncio.create_task(_read_stderr())
        wait_task = asyncio.create_task(process.wait())

        try:
            await asyncio.wait_for(
                asyncio.gather(stdout_task, stderr_task, wait_task),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            timed_out = True
            process.kill()
            await process.wait()
            await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)

        stdout_text = "\n".join(stdout_lines)
        stderr_text = "".join(stderr_lines)

        # Parse the output based on format
        if self.output_format == "stream-json":
            response = self._parse_stream_json(stdout_text, stderr_text, process.returncode)
        elif self.output_format == "json":
            response = self._parse_json(stdout_text, stderr_text, process.returncode)
        else:
            response = CLIResponse(
                success=process.returncode == 0,
                output=stdout_text,
                error=stderr_text if process.returncode != 0 else None,
            )

        if timed_out:
            timeout_msg = f"CLI task timed out after {timeout} seconds"
            response.success = False
            response.error = _clean_join_text(response.error, timeout_msg)
        return response

    def _parse_stream_json(self, stdout: str, stderr: str, returncode: int) -> CLIResponse:
        """Parse stream-json format output (newline-delimited JSON events)."""
        events = []
        output_parts = []
        tool_calls = []
        error = None

        for line in stdout.strip().split("\n"):
            if not line:
                continue
            try:
                event = json.loads(line)
                events.append(event)

                event_type = event.get("type")

                if event_type == "message" and event.get("role") == "assistant":
                    content = event.get("content", "")
                    if content:
                        output_parts.append(content)

                elif event_type == "tool_use":
                    tool_calls.append({
                        "tool_name": event.get("tool_name"),
                        "tool_id": event.get("tool_id"),
                        "parameters": event.get("parameters"),
                    })

                elif event_type == "tool_result":
                    # Match tool result to tool call
                    tool_id = event.get("tool_id")
                    for tc in tool_calls:
                        if tc.get("tool_id") == tool_id:
                            tc["result"] = event.get("output")
                            tc["status"] = event.get("status")
                            tc["error"] = event.get("error")

                elif event_type == "error":
                    error = event.get("message", "Unknown error")

                elif event_type == "result":
                    # Final result event
                    if event.get("status") != "success":
                        error = event.get("error", "Task failed")

            except json.JSONDecodeError:
                # Non-JSON line, might be debug output
                continue

        output = "".join(output_parts)

        return CLIResponse(
            success=returncode == 0 and error is None,
            output=output,
            error=error or (stderr if returncode != 0 else None),
            tool_calls=tool_calls if tool_calls else None,
        )

    def _parse_json(self, stdout: str, stderr: str, returncode: int) -> CLIResponse:
        """Parse single JSON output format."""
        try:
            data = json.loads(stdout)
            return CLIResponse(
                success=returncode == 0,
                output=data.get("response", stdout),
                error=data.get("error"),
            )
        except json.JSONDecodeError:
            return CLIResponse(
                success=returncode == 0,
                output=stdout,
                error=stderr if returncode != 0 else None,
            )

    async def run_command(self, command: str, timeout: int = 30) -> tuple[str, str, int]:
        """
        Run a shell command directly (bypass LLM).

        Args:
            command: Shell command to execute
            timeout: Maximum execution time in seconds

        Returns:
            Tuple of (stdout, stderr, return_code)
        """
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return "", "Command timed out", -1

        return (
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
            process.returncode or 0,
        )


# Convenience function for quick execution
async def run_cli_task(task: str, **kwargs) -> dict:
    """
    Quick helper to run a CLI task.

    Args:
        task: The task description
        **kwargs: Additional arguments for CLIAgent

    Returns:
        Result dict with success, result, error keys
    """
    agent = CLIAgent(**kwargs)
    return await agent.execute(task)
