"""Helpers for the /notebooklm LearnPack slash command."""

from __future__ import annotations

import re
from datetime import datetime


_NOTEBOOKLM_USAGE = """Usage: /notebooklm <topic|url|repo|kb topic|inbox name>

Create a NotebookLM learning pack with Study Guide, Slide Deck, Quiz,
Flashcards, Mind Map, summary, and wiki-ingest candidates.

Examples:
  /notebooklm vibe coding
  /notebooklm kb agentic engineering
  /notebooklm repo https://github.com/user/project
  /notebooklm url https://example.com/article
  /notebooklm inbox ai-memory"""


def notebooklm_usage() -> str:
    """Return user-facing usage for the /notebooklm command."""

    return _NOTEBOOKLM_USAGE


_KNOWN_SHARED_DIRS = (
    "macOS: /Users/myartings/Sync",
    "Linux: /home/myartings/Sync",
    r"Windows: C:\Users\myartings\Sync",
)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value.strip().lower())
    slug = slug.strip("-")
    return slug[:80] or "learnpack"


def _route_hint(args: str) -> str:
    lowered = args.strip().lower()
    if lowered.startswith("kb "):
        return (
            "Treat this as a local knowledge-base topic. Search/read the local "
            "knowledge base first and use the kb-notebooklm-bundler workflow "
            "when available."
        )
    if lowered.startswith("inbox "):
        return (
            "Treat this as a NotebookLM inbox request. Look under "
            "<shared-dir>/docs/notebooklm-inbox/<name>/ for source material."
        )
    if lowered.startswith("repo ") or "github.com/" in lowered:
        return (
            "Treat this as a repository source. Build or fetch a repo digest "
            "first, for example with Gitingest or an equivalent local digest."
        )
    if lowered.startswith("url ") or re.match(r"https?://", args.strip(), re.I):
        return "Treat this as a URL source. Fetch and convert it into clean source material first."
    return "Treat this as a topic. Search the local knowledge base first, then gather external sources if needed."


def build_notebooklm_learnpack_prompt(args: str) -> str:
    """Convert /notebooklm arguments into the standard agent task prompt.

    The slash command itself is intentionally a thin, discoverable entrypoint.
    The agent still performs source resolution, NotebookLM/bundler execution,
    artifact collection, and optional wiki-ingest review using normal tools.
    """

    topic_or_source = (args or "").strip()
    if not topic_or_source:
        return ""

    today = datetime.now().strftime("%Y-%m-%d")
    slug = _slugify(topic_or_source)
    shared_dirs = "\n".join(f"- {line}" for line in _KNOWN_SHARED_DIRS)
    route_hint = _route_hint(topic_or_source)

    return f"""Run the NotebookLM LearnPack workflow for: {topic_or_source}

Goal: make this topic/source easy to learn and review with NotebookLM. Keep the workflow simple and automated; choose sensible defaults without asking unless a privacy, login, paid-content, or destructive/external-publish decision is required.

Default outputs:
- Study Guide
- Slide Deck
- Quiz
- Flashcards
- Mind Map
- concise summary of key points
- `ingest-candidates.md` with stable wiki candidates

Default save location:
- Use the platform shared directory when known:
{shared_dirs}
- Save outputs under: <shared-dir>/docs/notebooklm-learning/{today}-{slug}/

Input routing:
- {route_hint}
- Preserve the user's original topic/source text exactly: {topic_or_source}

Knowledge-base policy:
- Do not directly overwrite long-term `wiki/` pages from NotebookLM output.
- Save learning artifacts and `ingest-candidates.md` first.
- Ask before formal wiki ingest unless the user explicitly requested 入库/写入 wiki.

Verification:
- Report concrete artifact paths/URLs that were created.
- If NotebookLM auth, quota, or automation is unavailable, give the exact blocker and the next command/action needed to fix it.
"""
