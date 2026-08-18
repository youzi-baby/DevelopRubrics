"""Run Jiawen experiments sequentially with isolated output folders.

Example:
    .venv\\Scripts\\python examples\\run-jiawen-experiments.py

By default this runs three scoring ablations:
    1. observation-only input, Qwen thinking disabled
    2. action + action_input input, Qwen thinking disabled
    3. observation-only input, Qwen thinking enabled

Each experiment receives a new folder under docs/experiments, such as
2026081801, 2026081802, and a generated config whose output paths point into
that folder.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "examples" / "jiawen_rubric_config.json"
DEFAULT_PLAN_PATH = PROJECT_ROOT / "examples" / "jiawen_experiment_plan.json"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "docs" / "experiments"

Config = dict[str, Any]


@dataclass(frozen=True)
class ExperimentSpec:
    name: str
    script: Path
    output_overrides: dict[str, str]
    fixed_overrides: dict[str, Any]


EXPERIMENTS: dict[str, ExperimentSpec] = {
    "generate": ExperimentSpec(
        name="generate",
        script=PROJECT_ROOT / "examples" / "generate-jiawen-rubrics.py",
        output_overrides={
            "rubric_path": "jiawen_gui_initial_rubric.json",
            "evidence_path": "jiawen_gui_initial_rubric.evidence.md",
            "raw_response_path": "jiawen_gui_initial_rubric.raw_response.txt",
        },
        fixed_overrides={},
    ),
    "eval-observation-no-thinking": ExperimentSpec(
        name="eval-observation-no-thinking",
        script=PROJECT_ROOT / "examples" / "evaluate-jiawen-rubrics.py",
        output_overrides={
            "evaluation_report_path": "jiawen_gui_eval_observation_no_thinking.md",
            "evaluation_jsonl_path": "jiawen_gui_eval_observation_no_thinking.jsonl",
        },
        fixed_overrides={
            "evaluation_resume_from_jsonl": False,
            "evaluation_include_action": False,
            "evaluation_include_action_input": False,
            "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
        },
    ),
    "eval-action-no-thinking": ExperimentSpec(
        name="eval-action-no-thinking",
        script=PROJECT_ROOT / "examples" / "evaluate-jiawen-rubrics.py",
        output_overrides={
            "evaluation_report_path": "jiawen_gui_eval_action_no_thinking.md",
            "evaluation_jsonl_path": "jiawen_gui_eval_action_no_thinking.jsonl",
        },
        fixed_overrides={
            "evaluation_resume_from_jsonl": False,
            "evaluation_include_action": True,
            "evaluation_include_action_input": True,
            "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
        },
    ),
    "eval-observation-thinking": ExperimentSpec(
        name="eval-observation-thinking",
        script=PROJECT_ROOT / "examples" / "evaluate-jiawen-rubrics.py",
        output_overrides={
            "evaluation_report_path": "jiawen_gui_eval_observation_thinking.md",
            "evaluation_jsonl_path": "jiawen_gui_eval_observation_thinking.jsonl",
        },
        fixed_overrides={
            "evaluation_resume_from_jsonl": False,
            "evaluation_include_action": False,
            "evaluation_include_action_input": False,
            "extra_body": {"chat_template_kwargs": {"enable_thinking": True}},
        },
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Jiawen experiment scripts sequentially into numbered folders."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"Base Jiawen config. Defaults to {DEFAULT_CONFIG_PATH}",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help=f"Experiment output root. Defaults to {DEFAULT_OUTPUT_ROOT}",
    )
    parser.add_argument(
        "--date",
        default=datetime.now().strftime("%Y%m%d"),
        help="Date prefix for experiment folders, e.g. 20260818. Defaults to today.",
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=DEFAULT_PLAN_PATH,
        help=f"Experiment plan JSON. Defaults to {DEFAULT_PLAN_PATH}",
    )
    parser.add_argument(
        "--experiments",
        default=None,
        help=(
            "Optional comma-separated experiment override. Available: "
            + ", ".join(sorted(EXPERIMENTS))
            + ". If omitted, experiments are read from --plan."
        ),
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue running later experiments after a failed experiment.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Create configs/manifests and print commands without running scripts.",
    )
    return parser.parse_args()


def load_config(path: Path) -> Config:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Config file must contain a JSON object: {path}")
    return data


def load_experiment_names(*, plan_path: Path, override: str | None) -> list[str]:
    if override:
        return [name.strip() for name in override.split(",") if name.strip()]

    data = json.loads(plan_path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [str(name).strip() for name in data if str(name).strip()]
    if isinstance(data, dict):
        configured = data.get("experiments", [])
        if not isinstance(configured, list):
            raise ValueError(f"experiments in plan must be a list: {plan_path}")
        return [str(name).strip() for name in configured if str(name).strip()]
    raise ValueError(f"Experiment plan must be a JSON object or list: {plan_path}")


def _relative_to_project(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def _existing_indices(output_root: Path, date_prefix: str) -> set[int]:
    pattern = re.compile(rf"^{re.escape(date_prefix)}(\d{{2}})$")
    indices: set[int] = set()
    if not output_root.exists():
        return indices
    for child in output_root.iterdir():
        if not child.is_dir():
            continue
        match = pattern.match(child.name)
        if match:
            indices.add(int(match.group(1)))
    return indices


def allocate_experiment_dirs(
    output_root: Path,
    *,
    date_prefix: str,
    count: int,
) -> list[Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    used = _existing_indices(output_root, date_prefix)
    dirs: list[Path] = []
    next_index = 1
    while len(dirs) < count:
        while next_index in used:
            next_index += 1
        used.add(next_index)
        dirs.append(output_root / f"{date_prefix}{next_index:02d}")
        next_index += 1
    return dirs


def build_experiment_config(base_config: Config, spec: ExperimentSpec, output_dir: Path) -> Config:
    config = dict(base_config)
    for key, filename in spec.output_overrides.items():
        config[key] = _relative_to_project(output_dir / filename)
    config.update(spec.fixed_overrides)
    return config


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_command(command: list[str], *, cwd: Path, log_path: Path) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log_file:
        process = subprocess.Popen(  # noqa: S603 - command uses whitelisted local scripts.
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="")
            log_file.write(line)
        return process.wait()


def main() -> int:
    args = parse_args()
    base_config_path = args.config if args.config.is_absolute() else PROJECT_ROOT / args.config
    plan_path = args.plan if args.plan.is_absolute() else PROJECT_ROOT / args.plan
    output_root = (
        args.output_root if args.output_root.is_absolute() else PROJECT_ROOT / args.output_root
    )
    base_config = load_config(base_config_path)
    experiment_names = load_experiment_names(plan_path=plan_path, override=args.experiments)
    unknown = [name for name in experiment_names if name not in EXPERIMENTS]
    if unknown:
        raise ValueError(f"Unknown experiment(s): {unknown}. Available: {sorted(EXPERIMENTS)}")

    output_dirs = allocate_experiment_dirs(
        output_root,
        date_prefix=str(args.date),
        count=len(experiment_names),
    )

    batch_manifest: list[dict[str, Any]] = []
    for name, output_dir in zip(experiment_names, output_dirs, strict=True):
        spec = EXPERIMENTS[name]
        output_dir.mkdir(parents=True, exist_ok=False)
        config = build_experiment_config(base_config, spec, output_dir)
        config_path = output_dir / "experiment_config.json"
        manifest_path = output_dir / "manifest.json"
        log_path = output_dir / "run.log"
        command = [
            sys.executable,
            _relative_to_project(spec.script),
            "--config",
            _relative_to_project(config_path),
        ]
        manifest = {
            "experiment_id": output_dir.name,
            "experiment_name": name,
            "script": _relative_to_project(spec.script),
            "base_config": _relative_to_project(base_config_path),
            "plan": _relative_to_project(plan_path),
            "generated_config": _relative_to_project(config_path),
            "log_path": _relative_to_project(log_path),
            "command": command,
            "status": "pending",
        }
        write_json(config_path, config)
        write_json(manifest_path, manifest)
        batch_manifest.append(manifest)

        print("")
        print(f"=== Running {output_dir.name}: {name} ===")
        print("Command:", " ".join(command))
        if args.dry_run:
            manifest["status"] = "dry-run"
            write_json(manifest_path, manifest)
            continue

        return_code = run_command(command, cwd=PROJECT_ROOT, log_path=log_path)
        manifest["return_code"] = return_code
        manifest["status"] = "completed" if return_code == 0 else "failed"
        write_json(manifest_path, manifest)
        if return_code != 0 and not args.continue_on_error:
            write_json(output_root / f"batch_{args.date}.last.json", batch_manifest)
            return return_code

    write_json(output_root / f"batch_{args.date}.last.json", batch_manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
