# From Abstraction to Action

Code, data and DSLs for **[From Abstraction to Action: DSLs for Natural Language Abstraction Interpretation and Execution](https://arxiv.org/abs/2610.28311)** (Amit Lisha and Reut Tsarfaty).

📄 Paper: [arXiv:2610.28311](https://arxiv.org/abs/2610.28311)

| Path | What it is |
|---|---|
| `hexagen/` | **HexaGen**, the human-curated DSL for the Hexagons board (Appendix E) |
| `minimal_hexagen.py`, `minimal_hexagen_api_spec.txt` | The **minimal API** that DSL induction starts from (Appendix F) |
| `induced_dsls/` | The two GPT-5.1 (High) all-at-once induced DSLs analysed in Section 7 and Table 4 (Run A, Run B) |
| `data/` | Hexagons splits `train/dev/test.jsonl` (Lachmy et al., 2022, *Draw Me a Flower*) and the prompts (Appendix G) |
| `gpt/experiment.py` | Hexagons evaluation: Tiles, Unrestricted Python, and DSL-based code generation (Section 5, Tables 1 and 3) |
| `gpt/library_generation/` | DSL induction pipeline: discovery, implementation, documentation (Section 7, Appendix H) |
| `cadquery_exp/` | Text2CAD experiment, including the 8-function CadQuery DSL in `prompts/abstraction_layer.py` (Section 6, Appendix C) |

## Setup

```bash
pip install -e .                     # core: HexaGen + Hexagons evaluation
pip install -e ".[induction]"        # + semantic-batching induction
pip install -e ".[text2cad]"         # + Text2CAD experiment
```

API keys come from the environment: `OPENAI_API_KEY` for GPT models, and `GEMINI_API_KEY` (or `GCP_PROJECT_ID` for Vertex AI) for Gemini models. Open-weight models were served with vLLM and are reached through `--base-url`.

## Using HexaGen

```python
from hexagen import Game, Tile, Circle

with Game() as g:
    c = Tile(5, 7).draw("green")
    flower = Circle(c, radius=1).draw("red") + c
    flower.copy_paste("down").recolor({"red": "green", "green": "red"})
```

`data/hexagen_api_spec.txt` is the API documentation given to the model.

## Hexagons evaluation (Tables 1 and 3)

Run all commands from the repository root. `--mode` selects the strategy:

| `--mode` | Strategy |
|---|---|
| `tiles-full` | Direct prediction |
| `python-full` | Unrestricted Python |
| `code-full` | DSL-based code generation |

```bash
# GPT-5.1 (High): all three strategies, 3 runs each, on the test set
python gpt/experiment.py --set test --mode tiles-full python-full code-full \
    --model gpt-5.1 --reasoning-effort high --repeats 3 --workers 8 --experiment-name gpt51-high

# Gemini (thinking level) and an open-weight model served by vLLM
python gpt/experiment.py --set test --mode code-full --model gemini-3.1-pro-preview --thinking-level high --repeats 3
python gpt/experiment.py --set test --mode code-full --model Qwen/Qwen3-30B-A3B-Thinking-2507 \
    --base-url http://localhost:8000/v1 --repeats 3

# Code generation over the minimal API, or over an induced DSL (Table 3)
python gpt/experiment.py --set test --mode code-full --model gpt-5.1 --reasoning-effort high \
    --lib-file minimal_hexagen.py --api-spec-file minimal_hexagen_api_spec.txt
python gpt/experiment.py --set test --mode code-full --model gpt-5.1 --reasoning-effort high \
    --lib-file induced_dsls/gpt-5.1_all-at-once_run_a/library.py \
    --api-spec-file induced_dsls/gpt-5.1_all-at-once_run_a/api_spec.txt
```

The defaults match the paper: temperature 0, 15K max output tokens, a 60-second execution timeout, and up to 3 attempts conditioned on the exception message. Results, generated programs and board plots are written to `results-<experiment-name>-<uuid>/`. Each run produces `<set>/all_<timestamp>.json`, which holds board-level F1 and exact match.

## DSL induction (Section 7)

```bash
# all-at-once (flat)
python gpt/library_generation/orchestrator.py --ablation singleshot \
    --train-data data/train_standard.jsonl --base-lib minimal_hexagen.py \
    --base-lib-docs minimal_hexagen_api_spec.txt --model gpt-5.1 --experiment-name gpt51-flat-r1

# arbitrary batches (default); add --semantic-batching for semantic batches
python gpt/library_generation/orchestrator.py \
    --train-data data/train_standard.jsonl --base-lib minimal_hexagen.py \
    --base-lib-docs minimal_hexagen_api_spec.txt --model gpt-5.1 --experiment-name gpt51-batches-r1
```

The induced library is written to `generated_libs/<name>/stage3/generated_library.py` and its documentation to `stage4/api_spec.txt`. Evaluate them with `--lib-file` / `--api-spec-file` as shown above.

## Text2CAD (Section 6)

Get the Text2CAD v1.1 annotations (Khan et al., 2024) into `data/text2cad_v1.1/` (`text2cad_v1.1.csv`, `train_test_val.json`). Get the Text-to-CadQuery gold programs (Xie and Ju, 2025) into `data/CQ/<folder>/<id>.py`. Then:

```bash
# generate and execute programs under each condition (raw CadQuery vs. the DSL)
python cadquery_exp/cq_experiment.py --model gemini-3.1-pro-preview --split test --max-examples 1000 --conditions direct
python cadquery_exp/cq_experiment.py --model gemini-3.1-pro-preview --split test --max-examples 1000 --conditions abstraction

# pairwise VLM judge (Qwen3.6-27B served by vLLM) between the two runs
python cadquery_exp/cq_compare.py --run-a results-<direct-run> --run-b results-<dsl-run> \
    --vlm-model <served-model-name> --base-url http://localhost:8000/v1
```

## Citation

```bibtex
@misc{lisha2026abstraction,
  title         = {From Abstraction to Action: DSLs for Natural Language Abstraction Interpretation and Execution},
  author        = {Lisha, Amit and Tsarfaty, Reut},
  year          = {2026},
  eprint        = {2610.28311},
  archivePrefix = {arXiv},
  url           = {https://arxiv.org/abs/2610.28311}
}
```
