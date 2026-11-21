"""Configuration and CLI argument parsing for experiments."""

from __future__ import annotations

import argparse


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for experiment execution."""
    p = argparse.ArgumentParser()

    p.add_argument(
        "--set",
        type=str,
        required=True,
        choices=["train", "dev", "test"],
        help="Run every task in a dataset split: 'train', 'dev' or 'test'",
    )
    p.add_argument(
        "--model",
        default="gpt-4o",
        help="Model name (e.g., 'gpt-5.1', 'gemini-3-pro-preview', or a model served "
             "by a local OpenAI-compatible endpoint via --base-url)",
    )
    p.add_argument("--temperature", type=float, default=0)
    p.add_argument("--max-tokens", type=int, default=15000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--top-p", type=float, default=None,
                   help="Nucleus sampling top_p (OpenAI-compatible endpoints only; default: server default)")
    p.add_argument("--top-k", type=int, default=None,
                   help="Top-k sampling (sent via extra_body; vLLM/local endpoints only)")
    p.add_argument("--min-p", type=float, default=None,
                   help="Min-p sampling (sent via extra_body; vLLM/local endpoints only)")
    p.add_argument(
        "--retries", type=int, default=3, help="Max attempts per task on execution errors (0 = unlimited)"
    )
    p.add_argument(
        "--mode",
        nargs="+",
        choices=["tiles-full", "python-full", "code-full"],
        default=["code-full"],
        help="tiles-full = direct tile prediction; "
        "python-full = unrestricted Python returning (row, col, color) tuples; "
        "code-full = Python over a DSL (HexaGen by default, see --lib-file/--api-spec-file)",
    )
    p.add_argument(
        "--repeats",
        type=int,
        default=1,
        help="Number of times to run each selected mode",
    )
    p.add_argument(
        "--workers",
        "-j",
        type=int,
        default=1,
        help="Number of tasks to run in parallel",
    )
    p.add_argument(
        "--exec-timeout",
        type=int,
        default=60,
        help="Seconds to wait for generated code before aborting (0 = no limit)",
    )
    p.add_argument(
        "--request-timeout",
        type=int,
        default=300,
        help="Seconds to wait for an LLM API call before aborting (default: 300).",
    )
    p.add_argument(
        "--experiment-name",
        type=str,
        help="Experiment name",
    )
    p.add_argument(
        "--api-spec-file",
        type=str,
        default=None,
        help="Path to custom API spec file (for testing generated libraries). "
        "If not specified, uses default hexagen_api_spec.txt",
    )
    p.add_argument(
        "--shared-system-prompt",
        type=str,
        default=None,
        help="Path to a replacement shared system prompt file (the preamble prepended to "
        "every mode's system prompt). Default: data/shared_system_prompt.txt",
    )
    p.add_argument(
        "--lib-file",
        type=str,
        default="hexagen/hexagen.py",
        help="Path to library implementation file (for testing generated libraries). "
        "Default: hexagen/hexagen.py",
    )
    p.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="Base URL for the LLM API (e.g., http://localhost:8000/v1 for local models)",
    )
    p.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="API key for the LLM provider (overrides environment variables)",
    )
    p.add_argument(
        "--resume",
        type=str,
        default=None,
        help="Resume from a previous results directory. Completed tasks are "
        "loaded from existing run_*.json files and skipped. "
        "Example: --resume results-my-experiment-{uuid}",
    )
    p.add_argument(
        "--reasoning-effort",
        type=str,
        default=None,
        choices=["low", "medium", "high"],
        help="Reasoning effort for OpenAI reasoning models (o1/o3/gpt-5.x). "
        "Default: None (use model default)",
    )
    p.add_argument(
        "--thinking-budget",
        type=int,
        default=None,
        help="Thinking budget (max tokens) for Gemini 2.5 thinking models. "
        "Default: None (no thinking config)",
    )
    p.add_argument(
        "--thinking-level",
        type=str,
        default=None,
        choices=["minimal", "low", "medium", "high"],
        help="Thinking level for Gemini 2.5/3.x models (minimal/low/medium/high). "
        "Default: None (use model default)",
    )
    return p.parse_args()
