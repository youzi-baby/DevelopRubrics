"""Tests for the Jiawen sequential experiment runner."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "examples" / "run-jiawen-experiments.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("run_jiawen_experiments", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["run_jiawen_experiments"] = module
    spec.loader.exec_module(module)
    return module


def test_allocate_experiment_dirs_skips_existing_indices(tmp_path):
    module = _load_module()
    (tmp_path / "2026081801").mkdir()
    (tmp_path / "2026081803").mkdir()
    (tmp_path / "other").mkdir()

    dirs = module.allocate_experiment_dirs(tmp_path, date_prefix="20260818", count=3)

    assert [path.name for path in dirs] == [
        "2026081802",
        "2026081804",
        "2026081805",
    ]


def test_load_experiment_names_from_plan_file(tmp_path):
    module = _load_module()
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps({"experiments": ["evaluate", "evaluate-no-thinking"]}),
        encoding="utf-8",
    )

    assert module.load_experiment_names(plan_path=plan_path, override=None) == [
        "evaluate",
        "evaluate-no-thinking",
    ]


def test_load_experiment_names_override_skips_plan(tmp_path):
    module = _load_module()
    missing_plan = tmp_path / "missing.json"

    assert module.load_experiment_names(
        plan_path=missing_plan,
        override="direct-judge,evaluate",
    ) == ["direct-judge", "evaluate"]


def test_build_evaluate_config_points_outputs_to_experiment_dir(tmp_path):
    module = _load_module()
    spec = module.EXPERIMENTS["evaluate"]
    config = module.build_experiment_config(
        {"evaluation_resume_from_jsonl": True, "model": "qwen"},
        spec,
        PROJECT_ROOT / "docs" / "experiments" / "2026081801",
    )

    assert config["model"] == "qwen"
    assert config["evaluation_resume_from_jsonl"] is False
    assert config["evaluation_report_path"] == "docs/experiments/2026081801/jiawen_gui_eval.md"
    assert config["evaluation_jsonl_path"] == "docs/experiments/2026081801/jiawen_gui_eval.jsonl"


def test_build_direct_judge_config_points_outputs_to_experiment_dir():
    module = _load_module()
    spec = module.EXPERIMENTS["direct-judge"]
    config = module.build_experiment_config(
        {"direct_judge_resume_from_jsonl": True},
        spec,
        PROJECT_ROOT / "docs" / "experiments" / "2026081802",
    )

    assert config["direct_judge_resume_from_jsonl"] is False
    assert config["direct_judge_jsonl_path"] == (
        "docs/experiments/2026081802/jiawen_direct_judge_baseline.jsonl"
    )
    assert config["direct_judge_raw_response_path"] == (
        "docs/experiments/2026081802/jiawen_direct_judge_baseline.raw_response.jsonl"
    )


def test_build_evaluate_no_thinking_config_disables_qwen_thinking():
    module = _load_module()
    spec = module.EXPERIMENTS["evaluate-no-thinking"]
    config = module.build_experiment_config(
        {
            "evaluation_resume_from_jsonl": True,
            "extra_body": {"chat_template_kwargs": {"enable_thinking": True}},
        },
        spec,
        PROJECT_ROOT / "docs" / "experiments" / "2026081803",
    )

    assert config["evaluation_resume_from_jsonl"] is False
    assert config["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}
    assert config["evaluation_report_path"] == (
        "docs/experiments/2026081803/jiawen_gui_eval_no_thinking.md"
    )
    assert config["evaluation_jsonl_path"] == (
        "docs/experiments/2026081803/jiawen_gui_eval_no_thinking.jsonl"
    )
