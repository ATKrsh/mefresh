import os
import sys
import time
import subprocess
import threading
from typing import List, Dict, Any, Optional, Callable
from .system_ops import SystemOps

class InstallerEngine:
    """
    Executes post-install software batches silently with zero popup windows,
    streaming real-time telemetry, stdout/stderr, and exit code analytics
    directly to the dashboard.
    """

    def __init__(self):
        self._is_running = False
        self._is_paused = False
        self._stop_requested = False
        self._current_process: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None

    def start_batch(
        self,
        package_queue: List[Dict[str, Any]],
        options: Dict[str, Any],
        event_callback: Callable[[str, Dict[str, Any]], None]
    ):
        """Starts asynchronous execution of the software deployment queue."""
        if self._is_running:
            return

        self._is_running = True
        self._is_paused = False
        self._stop_requested = False

        self._thread = threading.Thread(
            target=self._worker_loop,
            args=(package_queue, options, event_callback),
            daemon=True
        )
        self._thread.start()

    def pause(self):
        """Pauses execution between installation tasks."""
        self._is_paused = True

    def resume(self):
        """Resumes execution."""
        self._is_paused = False

    def cancel(self):
        """Stops the queue and terminates the active installer process if needed."""
        self._stop_requested = True
        self._is_running = False
        if self._current_process:
            try:
                self._current_process.terminate()
            except Exception:
                pass

    def _worker_loop(
        self,
        queue: List[Dict[str, Any]],
        options: Dict[str, Any],
        event_callback: Callable[[str, Dict[str, Any]], None]
    ):
        total_items = len(queue)
        completed_items = 0
        failed_items = 0
        start_time = time.time()

        event_callback("engine_started", {
            "total": total_items,
            "timestamp": time.strftime("%H:%M:%S")
        })

        # 1. Automatic Restore Point Creation
        if options.get("create_restore_point", True):
            event_callback("log", {
                "level": "INFO",
                "message": "[SAFETY SHIELD] Initializing Windows System Restore Point creation..."
            })
            ok, msg = SystemOps.create_restore_point("mefresh_PreDeployment")
            if ok:
                event_callback("log", {
                    "level": "SUCCESS",
                    "message": f"[SAFETY SHIELD] {msg}"
                })
            else:
                event_callback("log", {
                    "level": "WARNING",
                    "message": f"[SAFETY SHIELD] {msg} (Continuing with deployment)"
                })

        # 2. Iterate through package queue
        for idx, item in enumerate(queue):
            while self._is_paused and not self._stop_requested:
                time.sleep(0.5)

            if self._stop_requested:
                event_callback("log", {
                    "level": "WARNING",
                    "message": "[ENGINE] Deployment cancelled by operator."
                })
                break

            pkg_id = item.get("id", f"item_{idx+1}")
            pkg_name = item.get("name", "Unknown Software")
            file_path = item.get("absolute_path") or item.get("file_path", "")
            silent_args = item.get("silent_args", "")
            installer_type = item.get("installer_type", "Standard")

            event_callback("item_started", {
                "index": idx,
                "id": pkg_id,
                "name": pkg_name,
                "progress": round((completed_items / max(total_items, 1)) * 100, 1)
            })

            event_callback("log", {
                "level": "INFO",
                "message": f"[{idx+1}/{total_items}] Initiating silent install for: {pkg_name}"
            })

            if not os.path.exists(file_path):
                event_callback("log", {
                    "level": "ERROR",
                    "message": f"Installer binary not found: {file_path}"
                })
                failed_items += 1
                event_callback("item_finished", {
                    "index": idx,
                    "id": pkg_id,
                    "status": "FAILED",
                    "exit_code": -1,
                    "error": "Binary not found"
                })
                if options.get("stop_on_error", False):
                    break
                continue

            # Build command line based on installer type
            cmd_args = self._build_execution_command(file_path, silent_args)

            event_callback("log", {
                "level": "CMD",
                "message": f"Executing: {' '.join(cmd_args)}"
            })

            # Execute process silently with CREATE_NO_WINDOW
            try:
                creation_flags = 0
                if os.name == "nt":
                    creation_flags = subprocess.CREATE_NO_WINDOW

                item_start = time.time()
                self._current_process = subprocess.Popen(
                    cmd_args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    creationflags=creation_flags
                )

                # Stream stdout in real-time
                if self._current_process.stdout:
                    for line in iter(self._current_process.stdout.readline, ''):
                        if self._stop_requested:
                            break
                        clean_line = line.strip()
                        if clean_line:
                            event_callback("log", {
                                "level": "STDOUT",
                                "message": f"[{pkg_name}] {clean_line}"
                            })

                self._current_process.wait()
                exit_code = self._current_process.returncode
                self._current_process = None
                duration = round(time.time() - item_start, 1)

                # Windows installer standard success codes: 0 = Success, 3010 = Success (Reboot required)
                is_success = (exit_code == 0 or exit_code == 3010)

                if is_success:
                    completed_items += 1
                    status_text = "COMPLETED"
                    msg_level = "SUCCESS"
                    extra = " (Reboot pending)" if exit_code == 3010 else ""
                    event_callback("log", {
                        "level": msg_level,
                        "message": f"[+] {pkg_name} successfully installed in {duration}s{extra}."
                    })
                else:
                    failed_items += 1
                    status_text = "FAILED"
                    event_callback("log", {
                        "level": "ERROR",
                        "message": f"[-] {pkg_name} failed with Exit Code: {exit_code}"
                    })

                event_callback("item_finished", {
                    "index": idx,
                    "id": pkg_id,
                    "status": status_text,
                    "exit_code": exit_code,
                    "duration_sec": duration
                })

                if not is_success and options.get("stop_on_error", False):
                    event_callback("log", {
                        "level": "WARNING",
                        "message": "[ENGINE] Halting batch sequence due to 'Stop on Error' policy."
                    })
                    break

            except Exception as e:
                failed_items += 1
                event_callback("log", {
                    "level": "ERROR",
                    "message": f"Execution error on {pkg_name}: {str(e)}"
                })
                event_callback("item_finished", {
                    "index": idx,
                    "id": pkg_id,
                    "status": "FAILED",
                    "exit_code": -1,
                    "error": str(e)
                })

        total_duration = round(time.time() - start_time, 1)
        self._is_running = False

        event_callback("engine_completed", {
            "total": total_items,
            "completed": completed_items,
            "failed": failed_items,
            "duration_sec": total_duration,
            "timestamp": time.strftime("%H:%M:%S")
        })

    def _build_execution_command(self, file_path: str, silent_args: str) -> List[str]:
        """Constructs safe execution command line array for Windows."""
        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".msi":
            # MSIEXEC execution
            cmd = ["msiexec.exe", "/i", file_path]
            if silent_args:
                cmd.extend(silent_args.split())
            else:
                cmd.extend(["/qn", "/norestart"])
            return cmd
        elif ext in [".bat", ".cmd"]:
            # Batch script execution
            cmd = ["cmd.exe", "/c", file_path]
            if silent_args:
                cmd.extend(silent_args.split())
            return cmd
        elif ext == ".ps1":
            # PowerShell script execution
            cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", file_path]
            if silent_args:
                cmd.extend(silent_args.split())
            return cmd
        else:
            # Standard EXE execution
            cmd = [file_path]
            if silent_args:
                cmd.extend(silent_args.split())
            return cmd
