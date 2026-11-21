"""Tiles-full mode runner - predict all tiles at once for all instructions."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from llm_wrapper import call_llm
from runner_utils import parse_tile_actions, save_plot
from constants.constants import COLORS, WIDTH, HEIGHT
from metrics import evaluate_prediction


def build_tiles_full_prompt(user_tmpl: str, instructions: List[str]) -> str:
    """Build the prompt for tiles-full mode."""
    instructions_block = "\n".join(f"{i+1}. {txt}" for i, txt in enumerate(instructions))
    return (
        user_tmpl.replace("{HISTORY_BLOCK}", "(none – full run)")
        .replace("{NEXT_STEP}", instructions_block)
    )


def run_tiles_full(
    cfg: argparse.Namespace,
    sys_prompt: str,
    user_tmpl: str,
    instructions: List[str],
    gold_final: List[int],
    image_path: Optional[Path],
    task_dir: Path,
    run_ts: str,
    initial_board: List[int] = None,
    width: int = None,
    height: int = None,
) -> Dict:
    """
    Single-shot prompt that passes ALL instructions as one block.
    Model predicts tiles directly for all instructions combined.
    """
    width = WIDTH if width is None else width
    height = HEIGHT if height is None else height

    prompt = build_tiles_full_prompt(user_tmpl, instructions)
    resp = call_llm(
        prompt=prompt,
        system_prompt=sys_prompt,
        model=cfg.model,
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
        seed=cfg.seed,
        images=[str(image_path)] if image_path else None,
        reasoning_effort=getattr(cfg, "reasoning_effort", None),
        thinking_budget=getattr(cfg, "thinking_budget", None),
        thinking_level=getattr(cfg, "thinking_level", None),
    )

    _, tiles = parse_tile_actions(resp["text"])

    board = [0] * (width * height)
    for r, c, col in tiles:
        if 1 <= r <= height and 1 <= c <= width and col in COLORS:
            board[(r - 1) * width + (c - 1)] = COLORS.index(col)

    # In full mode the model predicts the entire board from scratch, so the
    # "previous" state is blank for both pred and gold (action F1 == board F1).
    blank_board = [0] * (width * height)
    metrics = evaluate_prediction(blank_board, board, blank_board, gold_final)

    log = {
        "attempt": 1,
        "tiles": tiles,
        "valid": True,
        "usage": resp["usage"],
        **({"agent_info": resp["agent_info"]} if "agent_info" in resp else {}),
        **metrics,
    }

    save_plot(board, gold_final, task_dir / f"{run_ts}_plot_tiles_full_01.png")
    return log
