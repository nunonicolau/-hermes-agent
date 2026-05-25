"""
Process Utilities -- Cross-platform process management utilities.

Provides unified process termination, process tree handling,
and PID management utilities that work across Windows, Linux, and macOS.

Usage:
    from tools.process_utils import terminate_process_tree, pid_exists

    # Terminate a process and all its children
    terminate_process_tree(pid)

    # Check if a PID is alive
    if pid_exists(pid):
        print(f"PID {pid} is running")
"""

import os
import platform
import signal
import subprocess
from typing import Optional

_IS_WINDOWS = platform.system() == "Windows"


def terminate_process_tree(
    pid: int,
    force: bool = False,
    include_children: bool = True,
) -> None:
    """Terminate a process (cross-platform).

    Args:
        pid: Process ID to terminate
        force: If True, use SIGKILL/taskkill /F instead of SIGTERM
        include_children: If True, also terminate child processes
    """
    if _IS_WINDOWS:
        _terminate_windows(pid, force, include_children)
    else:
        _terminate_posix(pid, force, include_children)


def _terminate_windows(pid: int, force: bool, include_children: bool) -> None:
    """Windows-specific process termination."""
    from hermes_cli._subprocess_compat import windows_hide_flags

    flags = ["/PID", str(pid)]

    if include_children:
        flags.append("/T")  # Tree kill

    if force:
        flags.append("/F")  # Force

    try:
        subprocess.run(
            ["taskkill"] + flags,
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=windows_hide_flags(),
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        _fallback_kill(pid, force)


def _terminate_posix(pid: int, force: bool, include_children: bool) -> None:
    """POSIX-specific process termination."""
    if not include_children:
        _fallback_kill(pid, force)
        return

    try:
        import psutil

        parent = psutil.Process(pid)
        sig = signal.SIGKILL if force else signal.SIGTERM

        # Terminate children first (leaf-up order)
        for child in parent.children(recursive=True):
            try:
                child.send_signal(sig)
            except psutil.NoSuchProcess:
                pass

        # Terminate parent
        parent.send_signal(sig)
    except psutil.NoSuchProcess:
        return
    except (OSError, PermissionError, ImportError):
        _fallback_kill(pid, force)


def _fallback_kill(pid: int, force: bool) -> None:
    """Fallback to simple os.kill when advanced methods fail."""
    try:
        sig = signal.SIGKILL if force else signal.SIGTERM
        os.kill(pid, sig)
    except (OSError, ProcessLookupError, PermissionError):
        pass


def pid_exists(pid: int) -> bool:
    """Check if a PID is alive (cross-platform safe).

    Note: os.kill(pid, 0) is NOT a no-op on Windows (bpo-14484).
    CPython's Windows implementation treats sig=0 as CTRL_C_EVENT,
    which sends Ctrl+C to the entire console process group.

    On POSIX systems, os.kill(pid, 0) returns True for zombie processes,
    so we use psutil to filter them out when available.

    Implementation: prefer psutil (hard dependency), fallback to ctypes
    on Windows or os.kill(pid, 0) on POSIX.
    """
    try:
        import psutil
        exists = psutil.pid_exists(pid)
        if not exists:
            return False
        if not _IS_WINDOWS:
            try:
                proc = psutil.Process(pid)
                return proc.status() != psutil.STATUS_ZOMBIE
            except psutil.NoSuchProcess:
                return False
        return True
    except ImportError:
        pass

    if _IS_WINDOWS:
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.OpenProcess.restype = ctypes.c_void_p
            kernel32.WaitForSingleObject.restype = ctypes.c_uint
            kernel32.GetLastError.restype = ctypes.c_uint
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            SYNCHRONIZE = 0x100000
            WAIT_TIMEOUT = 0x00000102
            ERROR_INVALID_PARAMETER = 87
            ERROR_ACCESS_DENIED = 5
            handle = kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid
            )
            if not handle:
                err = kernel32.GetLastError()
                if err == ERROR_INVALID_PARAMETER:
                    return False
                if err == ERROR_ACCESS_DENIED:
                    return True
                return False
            try:
                wait_result = kernel32.WaitForSingleObject(handle, 0)
                return wait_result == WAIT_TIMEOUT
            finally:
                kernel32.CloseHandle(handle)
        except (OSError, AttributeError):
            try:
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                return str(pid) in result.stdout
            except Exception:
                return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False
