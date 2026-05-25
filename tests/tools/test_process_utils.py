"""Tests for tools/process_utils.py — Cross-platform process management utilities."""

import os
import platform
import signal
import subprocess
import sys
import time
import pytest
from unittest.mock import MagicMock, patch, call

from tools.process_utils import terminate_process_tree, pid_exists, _IS_WINDOWS


class TestPidExists:
    """Tests for pid_exists() function."""

    def test_pid_exists_returns_true_for_self(self):
        """pid_exists should return True for current process."""
        assert pid_exists(os.getpid()) is True

    def test_pid_exists_returns_false_for_nonexistent_pid(self):
        """pid_exists should return False for a PID that doesn't exist."""
        nonexistent_pid = 999999
        assert pid_exists(nonexistent_pid) is False

    def test_pid_exists_handles_zero(self):
        """pid_exists should handle PID 0 gracefully.
        
        Note: On macOS, PID 0 is the launchd process and exists.
        On Linux, PID 0 is usually the idle task and may exist.
        """
        # Just verify it doesn't raise and returns a boolean
        result = pid_exists(0)
        assert isinstance(result, bool)


class TestTerminateProcessTree:
    """Tests for terminate_process_tree() function."""

    def test_terminate_process_tree_handles_nonexistent_pid(self):
        """terminate_process_tree should not raise for non-existent PID."""
        terminate_process_tree(999999, force=False)

    def test_terminate_process_tree_without_children(self):
        """Test terminate_process_tree with include_children=False."""
        with patch("tools.process_utils.os.kill") as mock_kill:
            terminate_process_tree(12345, force=False, include_children=False)

    def test_terminate_process_tree_force_true(self):
        """Test terminate_process_tree with force=True."""
        with patch("tools.process_utils.os.kill") as mock_kill:
            terminate_process_tree(12345, force=True, include_children=False)
            if not _IS_WINDOWS:
                mock_kill.assert_called_once_with(12345, signal.SIGKILL)

    def test_terminate_process_tree_force_false(self):
        """Test terminate_process_tree with force=False."""
        with patch("tools.process_utils.os.kill") as mock_kill:
            terminate_process_tree(12345, force=False, include_children=False)
            if not _IS_WINDOWS:
                mock_kill.assert_called_once_with(12345, signal.SIGTERM)

    @pytest.mark.skipif(_IS_WINDOWS, reason="POSIX-specific test")
    def test_posix_terminate_with_children(self):
        """Test POSIX process tree termination with children."""
        with patch.dict(sys.modules, {"psutil": MagicMock()}) as mock_modules:
            mock_psutil = MagicMock()
            mock_modules["psutil"] = mock_psutil
            
            mock_process = MagicMock()
            mock_child1 = MagicMock()
            mock_child2 = MagicMock()
            mock_psutil.Process.return_value = mock_process
            mock_process.children.return_value = [mock_child1, mock_child2]

            terminate_process_tree(12345, force=False, include_children=True)

            mock_child1.send_signal.assert_called_once_with(signal.SIGTERM)
            mock_child2.send_signal.assert_called_once_with(signal.SIGTERM)
            mock_process.send_signal.assert_called_once_with(signal.SIGTERM)

    @pytest.mark.skipif(_IS_WINDOWS, reason="POSIX-specific test")
    def test_posix_terminate_force_with_children(self):
        """Test POSIX process tree termination with force=True."""
        with patch.dict(sys.modules, {"psutil": MagicMock()}) as mock_modules:
            mock_psutil = MagicMock()
            mock_modules["psutil"] = mock_psutil
            
            mock_process = MagicMock()
            mock_child = MagicMock()
            mock_psutil.Process.return_value = mock_process
            mock_process.children.return_value = [mock_child]

            terminate_process_tree(12345, force=True, include_children=True)

            mock_child.send_signal.assert_called_once_with(signal.SIGKILL)
            mock_process.send_signal.assert_called_once_with(signal.SIGKILL)

    @pytest.mark.skipif(not _IS_WINDOWS, reason="Windows-specific test")
    def test_windows_terminate_with_children(self):
        """Test Windows process tree termination."""
        with patch("tools.process_utils.subprocess.run") as mock_run:
            terminate_process_tree(12345, force=False, include_children=True)

            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "/PID" in args
            assert "12345" in args
            assert "/T" in args
            assert "/F" not in args

    @pytest.mark.skipif(not _IS_WINDOWS, reason="Windows-specific test")
    def test_windows_terminate_force(self):
        """Test Windows process termination with force=True."""
        with patch("tools.process_utils.subprocess.run") as mock_run:
            terminate_process_tree(12345, force=True, include_children=True)

            args = mock_run.call_args[0][0]
            assert "/F" in args

    def test_terminate_handles_no_permission(self):
        """terminate_process_tree should handle PermissionError gracefully."""
        with patch("tools.process_utils.os.kill", side_effect=PermissionError):
            terminate_process_tree(12345, force=False, include_children=False)

    def test_terminate_handles_os_error(self):
        """terminate_process_tree should handle OSError gracefully."""
        with patch("tools.process_utils.os.kill", side_effect=OSError):
            terminate_process_tree(12345, force=False, include_children=False)


class TestProcessTerminationIntegration:
    """Integration tests for process termination."""

    def _spawn_sleep(self, seconds: float = 5) -> subprocess.Popen:
        """Spawn a portable short-lived Python sleep process."""
        return subprocess.Popen(
            [sys.executable, "-c", f"import time; time.sleep({seconds})"],
        )

    def test_terminate_actual_process(self):
        """Test that terminate_process_tree actually terminates a real process."""
        proc = self._spawn_sleep(60)
        try:
            assert pid_exists(proc.pid) is True
            terminate_process_tree(proc.pid, force=False)
            time.sleep(0.1)
            proc.wait(timeout=1)
            assert proc.returncode is not None
        finally:
            try:
                proc.kill()
                proc.wait(timeout=1)
            except Exception:
                pass

    def test_terminate_actual_process_with_children(self):
        """Test that terminate_process_tree terminates child processes."""
        import psutil
        
        child_script = """
import subprocess
import sys
import time

child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
print(f"Child PID: {child.pid}", flush=True)
time.sleep(60)
"""
        proc = subprocess.Popen([sys.executable, "-c", child_script], stdout=subprocess.PIPE)
        
        try:
            time.sleep(0.5)
            line = proc.stdout.readline().decode().strip()
            
            child_pid = None
            if "Child PID:" in line:
                child_pid = int(line.split(":")[1].strip())
            
            assert pid_exists(proc.pid) is True
            
            terminate_process_tree(proc.pid, force=True)
            
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline and pid_exists(proc.pid):
                time.sleep(0.1)
            
            assert pid_exists(proc.pid) is False, f"Parent PID {proc.pid} should be terminated"
            
            if child_pid:
                deadline = time.monotonic() + 2.0
                while time.monotonic() < deadline and pid_exists(child_pid):
                    time.sleep(0.1)
                assert pid_exists(child_pid) is False, f"Child PID {child_pid} should be terminated"
        finally:
            try:
                # Cleanup any remaining processes
                if proc.poll() is None:
                    try:
                        parent = psutil.Process(proc.pid)
                        for child in parent.children(recursive=True):
                            child.kill()
                        proc.kill()
                    except (psutil.NoSuchProcess, OSError):
                        pass
                proc.wait(timeout=1)
            except Exception:
                pass
