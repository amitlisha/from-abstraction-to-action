from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

from gpt.runner_utils import DATA_DIR


def build_prompts(
    mode: str,
    api_spec_file: Optional[str] = None,
    shared_system_prompt: Optional[str] = None,
) -> Tuple[str, str]:
    """Load system and user templates for the selected mode.

    Args:
        mode: 'tiles-full' (direct prediction), 'python-full' (unrestricted Python)
              or 'code-full' (code over a DSL).
        api_spec_file: API spec injected into the code-full system prompt.
                       Defaults to data/hexagen_api_spec.txt.
        shared_system_prompt: Optional replacement for data/shared_system_prompt.txt.

    Returns:
        Tuple of (system_prompt, user_template)
    """
    shared_sys_p = Path(shared_system_prompt) if shared_system_prompt else DATA_DIR / "shared_system_prompt.txt"

    if mode == "tiles-full":
        sys_p, user_p = DATA_DIR / "tiles_system_prompt.txt", DATA_DIR / "tiles_user_message.txt"
        tags = ["{HISTORY_BLOCK}", "{NEXT_STEP}"]
    elif mode == "python-full":
        sys_p, user_p = DATA_DIR / "python_system_prompt.txt", DATA_DIR / "python_user_message.txt"
        tags = ["{HISTORY_BLOCK}", "{NEXT_STEP}"]
    elif mode == "code-full":
        sys_p, user_p = DATA_DIR / "code_system_prompt.txt", DATA_DIR / "code_user_message_template.txt"
        tags = ["{HISTORY_BLOCK}", "{NEXT_STEP}", "{CODE_SO_FAR}"]
    else:
        raise ValueError(f"Unknown mode: {mode}")

    system_tmpl = f"{shared_sys_p.read_text()}\n\n{sys_p.read_text()}"
    user_tmpl = user_p.read_text()

    if mode == "code-full":
        api_spec_path = Path(api_spec_file) if api_spec_file else DATA_DIR / "hexagen_api_spec.txt"
        if not api_spec_path.exists():
            raise FileNotFoundError(f"API spec file not found: {api_spec_path}")
        system_tmpl += f"\n\n{api_spec_path.read_text()}"

    for tag in tags:
        if tag not in user_tmpl:
            raise ValueError(f"{user_p.name} missing placeholder {tag}")
    return system_tmpl, user_tmpl
