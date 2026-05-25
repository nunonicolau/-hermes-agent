"""Tests for the /notebooklm LearnPack helper."""

from hermes_cli.notebooklm_command import (
    build_notebooklm_learnpack_prompt,
    notebooklm_usage,
)


def test_notebooklm_usage_mentions_common_modes():
    usage = notebooklm_usage()
    assert "/notebooklm <topic|url|repo|kb topic|inbox name>" in usage
    assert "/notebooklm kb agentic engineering" in usage
    assert "/notebooklm repo https://github.com/user/project" in usage


def test_empty_payload_returns_empty_prompt():
    assert build_notebooklm_learnpack_prompt("") == ""
    assert build_notebooklm_learnpack_prompt("   ") == ""


def test_prompt_preserves_payload_and_defaults():
    prompt = build_notebooklm_learnpack_prompt("kb vibe coding")
    assert "Run the NotebookLM LearnPack workflow for: kb vibe coding" in prompt
    assert "Study Guide" in prompt
    assert "Slide Deck" in prompt
    assert "Flashcards" in prompt
    assert "<shared-dir>/docs/notebooklm-learning/" in prompt
    assert "/Users/myartings/Sync" in prompt
    assert "/home/myartings/Sync" in prompt
    assert r"C:\Users\myartings\Sync" in prompt
    assert "Do not directly overwrite long-term `wiki/` pages" in prompt


def test_prompt_routes_inbox_to_shared_dir_placeholder():
    prompt = build_notebooklm_learnpack_prompt("inbox ai-memory")
    assert "<shared-dir>/docs/notebooklm-inbox/<name>/" in prompt


def test_prompt_preserves_chinese_payload():
    prompt = build_notebooklm_learnpack_prompt("知识库里的 agent memory")
    assert "知识库里的 agent memory" in prompt
