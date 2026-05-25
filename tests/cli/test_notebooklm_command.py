"""Tests for the /notebooklm CLI command path."""

from queue import Queue
from unittest.mock import MagicMock, patch


def _make_cli():
    from cli import HermesCLI

    cli = HermesCLI.__new__(HermesCLI)
    cli.config = {"quick_commands": {}}
    cli.console = MagicMock()
    cli.agent = None
    cli.conversation_history = []
    cli.session_id = "test-session"
    cli._pending_input = Queue()
    return cli


def test_notebooklm_with_payload_queues_learnpack_prompt():
    cli = _make_cli()

    with patch("cli._cprint") as cprint:
        assert cli.process_command("/notebooklm kb vibe coding") is True

    prompt = cli._pending_input.get_nowait()
    assert "Run the NotebookLM LearnPack workflow for: kb vibe coding" in prompt
    assert "<shared-dir>/docs/notebooklm-learning/" in prompt
    printed = " ".join(str(call) for call in cprint.call_args_list)
    assert "NotebookLM LearnPack queued" in printed


def test_notebooklm_without_payload_prints_usage_only():
    cli = _make_cli()

    with patch("cli._cprint") as cprint:
        assert cli.process_command("/notebooklm") is True

    assert cli._pending_input.empty()
    printed = " ".join(str(call) for call in cprint.call_args_list)
    assert "Usage: /notebooklm" in printed
