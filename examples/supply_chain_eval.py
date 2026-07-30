"""AdaRubric — Multi-Step API Orchestration Evaluation.

Demonstrates evaluating multiple agent trajectories for a complex
procurement API-chaining task, with composite filtering (AbsoluteThreshold
+ DimensionAwareFilter). Shows how the DimensionAwareFilter prevents a
high average score from masking a catastrophic failure on a single dimension.

Usage:
    export OPENAI_API_KEY="sk-..."
    python examples/supply_chain_eval.py

For an OpenAI-compatible local model server on PowerShell:
    $env:ADARUBRIC_BASE_URL="http://localhost:8000/v1"
    $env:ADARUBRIC_API_KEY="EMPTY"
    $env:ADARUBRIC_MODEL="your-local-model-name"
    .venv\\Scripts\\python examples\\supply_chain_eval.py

Rubric persistence:
    By default, the script loads an existing rubric from
    docs/rubrics/supply_chain_rubric.json. If the file does not exist, it
    generates a rubric once and saves it there. Set ADARUBRIC_REGENERATE_RUBRIC=1
    to force regeneration, or ADARUBRIC_RUBRIC_PATH to use a different JSON file.

Stability evaluation:
    By default, the script runs evaluation 10 times against the same persisted
    rubric and writes a stability report. Set ADARUBRIC_EVAL_RUNS to change the
    repeat count.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from pathlib import Path
from statistics import mean, pstdev

from adarubric import (
    AdaRubricPipeline,
    DynamicRubric,
    PipelineResult,
    TaskDescription,
    Trajectory,
    TrajectoryStep,
)
from adarubric.evaluator.aggregator import ConfidenceNormalizedAggregator
from adarubric.evaluator.trajectory_evaluator import LLMTrajectoryEvaluator
from adarubric.filter.threshold import (
    AbsoluteThresholdFilter,
    CompositeFilter,
    DimensionAwareFilter,
)
from adarubric.generator.llm_generator import LLMRubricGenerator
from adarubric.llm.openai_client import OpenAIClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUBRIC_PATH = PROJECT_ROOT / "docs" / "rubrics" / "supply_chain_rubric.json"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "docs" / "evaluation_outputs"


def _rubric_path_from_env() -> Path:
    configured = os.environ.get("ADARUBRIC_RUBRIC_PATH")
    if not configured:
        return DEFAULT_RUBRIC_PATH
    path = Path(configured)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _should_regenerate_rubric() -> bool:
    value = os.environ.get("ADARUBRIC_REGENERATE_RUBRIC", "")
    return value.strip().lower() in {"1", "true", "yes", "y"}


def _report_path_from_env() -> Path:
    configured = os.environ.get("ADARUBRIC_REPORT_PATH")
    if configured:
        path = Path(configured)
        return path if path.is_absolute() else PROJECT_ROOT / path

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return DEFAULT_REPORT_DIR / f"supply_chain_eval_{timestamp}.txt"


def _eval_runs_from_env() -> int:
    configured = os.environ.get("ADARUBRIC_EVAL_RUNS", "10")
    try:
        runs = int(configured)
    except ValueError:
        raise ValueError(f"ADARUBRIC_EVAL_RUNS must be an integer, got {configured!r}") from None
    if runs < 1:
        raise ValueError(f"ADARUBRIC_EVAL_RUNS must be >= 1, got {runs}")
    return runs


async def load_or_generate_rubric(
    pipeline: AdaRubricPipeline,
    task: TaskDescription,
    *,
    rubric_path: Path,
    num_dimensions: int = 5,
) -> DynamicRubric:
    if rubric_path.exists() and not _should_regenerate_rubric():
        rubric = DynamicRubric.model_validate_json(rubric_path.read_text(encoding="utf-8"))
        print(f"Loaded rubric from {rubric_path}")
        return rubric

    rubric = await pipeline.generate_rubric(task, num_dimensions=num_dimensions)
    rubric_path.parent.mkdir(parents=True, exist_ok=True)
    rubric_path.write_text(rubric.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"Generated and saved rubric to {rubric_path}")
    return rubric


def _format_run_result(result: PipelineResult, run_number: int) -> list[str]:
    lines: list[str] = []
    lines.append(f"## Run {run_number}")
    for ev in result.all_evaluations:
        status = "PASS" if ev.passed_threshold else "FAIL"
        lines.append("")
        lines.append(f"--- {ev.trajectory_id} [{status}] score={ev.global_score:.2f} ---")
        for name, score in ev.dimension_global_scores.items():
            lines.append(f"  {name}: {score:.2f}")

    lines.append("")
    lines.append(f"Survival rate: {result.survival_rate:.0%}")
    lines.append(f"Survivors: {[e.trajectory_id for e in result.surviving_evaluations]}")
    return lines


def _format_stability_summary(results: list[PipelineResult]) -> list[str]:
    lines: list[str] = []
    lines.append("## Stability Summary")

    scores_by_traj: dict[str, list[float]] = {}
    pass_counts: dict[str, int] = {}
    dimension_scores_by_traj: dict[str, dict[str, list[float]]] = {}

    for result in results:
        for ev in result.all_evaluations:
            scores_by_traj.setdefault(ev.trajectory_id, []).append(ev.global_score)
            pass_counts[ev.trajectory_id] = pass_counts.get(ev.trajectory_id, 0) + int(
                ev.passed_threshold
            )
            dim_scores = dimension_scores_by_traj.setdefault(ev.trajectory_id, {})
            for dim_name, dim_score in ev.dimension_global_scores.items():
                dim_scores.setdefault(dim_name, []).append(dim_score)

    for trajectory_id, scores in scores_by_traj.items():
        score_std = pstdev(scores) if len(scores) > 1 else 0.0
        lines.append("")
        lines.append(f"--- {trajectory_id} ---")
        lines.append(
            "global_score: "
            f"mean={mean(scores):.3f}, std={score_std:.3f}, "
            f"min={min(scores):.3f}, max={max(scores):.3f}, "
            f"pass={pass_counts.get(trajectory_id, 0)}/{len(scores)}"
        )

        for dim_name, dim_scores in dimension_scores_by_traj.get(trajectory_id, {}).items():
            dim_std = pstdev(dim_scores) if len(dim_scores) > 1 else 0.0
            lines.append(
                f"  {dim_name}: mean={mean(dim_scores):.3f}, "
                f"std={dim_std:.3f}, min={min(dim_scores):.3f}, max={max(dim_scores):.3f}"
            )

    return lines


def build_report(results: list[PipelineResult], *, rubric_path: Path) -> str:
    if not results:
        raise ValueError("At least one PipelineResult is required")

    first_result = results[0]
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("AdaRubric - Multi-Step API Orchestration Stability Evaluation")
    lines.append("=" * 60)
    lines.append(f"Rubric file: {rubric_path}")
    lines.append(f"Evaluation runs: {len(results)}")
    lines.append("")
    lines.append(f"Rubric Dimensions ({len(first_result.rubric.dimensions)}):")
    for dim in first_result.rubric.dimensions:
        lines.append(f"  [{dim.weight:.1f}x] {dim.name}: {dim.description[:70]}...")

    lines.append("")
    lines.append(f"Rationale: {first_result.rubric.generation_rationale[:200]}")
    lines.append("")
    lines.extend(_format_stability_summary(results))

    for run_number, result in enumerate(results, 1):
        lines.append("")
        lines.extend(_format_run_result(result, run_number))

    return "\n".join(lines)


def save_report(report: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report + "\n", encoding="utf-8")


async def main() -> None:
    task = TaskDescription(
        task_id="sc-001",
        instruction=(
            "You are a procurement agent. Find 3 suppliers of industrial-grade "
            "ball bearings (6205-2RS type) in the EU, request quotes for 10,000 "
            "units, compare total cost including shipping, and recommend the "
            "best value option considering both price and lead time."
        ),
        domain="Procurement API Orchestration",
        complexity="complex",
        expected_tools=[
            "supplier_search",
            "request_quote",
            "shipping_calculator",
            "compare_options",
            "submit_recommendation",
        ],
        context={
            "budget_eur": 50000,
            "delivery_deadline_days": 30,
            "quality_standard": "ISO 9001",
        },
    )

    good_trajectory = Trajectory(
        trajectory_id="sc-traj-good",
        task_id="sc-001",
        steps=[
            TrajectoryStep(
                step_id=0,
                thought="Search for EU-based ball bearing suppliers with ISO 9001 cert",
                action="supplier_search",
                action_input={
                    "product": "6205-2RS ball bearing",
                    "region": "EU",
                    "certification": "ISO 9001",
                },
                observation=(
                    "Found 5 suppliers: SKF (SE), FAG/Schaeffler (DE), "
                    "NTN-SNR (FR), NSK (UK), ZKL (CZ)"
                ),
            ),
            TrajectoryStep(
                step_id=1,
                thought="Request quotes from top 3 by reputation",
                action="request_quote",
                action_input={
                    "suppliers": ["SKF", "Schaeffler", "NTN-SNR"],
                    "quantity": 10000,
                    "part": "6205-2RS",
                },
                observation=(
                    "SKF: 3.20 EUR/unit, MOQ 5000, lead 14d | "
                    "Schaeffler: 2.85 EUR/unit, MOQ 10000, lead 21d | "
                    "NTN-SNR: 3.05 EUR/unit, MOQ 1000, lead 10d"
                ),
            ),
            TrajectoryStep(
                step_id=2,
                thought="Calculate shipping costs for each",
                action="shipping_calculator",
                action_input={
                    "origins": ["Stockholm", "Herzogenaurach", "Annecy"],
                    "destination": "customer_warehouse",
                    "weight_kg": 850,
                },
                observation="SKF: 1200 EUR | Schaeffler: 800 EUR | NTN-SNR: 950 EUR",
            ),
            TrajectoryStep(
                step_id=3,
                thought="Compare total costs and factor in lead times",
                action="compare_options",
                action_input="structured comparison",
                observation=(
                    "Total cost — SKF: 33,200 EUR (14d) | "
                    "Schaeffler: 29,300 EUR (21d) | NTN-SNR: 31,450 EUR (10d)"
                ),
            ),
            TrajectoryStep(
                step_id=4,
                thought=(
                    "Schaeffler is cheapest but 21d lead time is close to the 30d deadline. "
                    "NTN-SNR offers fastest delivery with moderate cost. "
                    "Recommending Schaeffler with NTN-SNR as backup."
                ),
                action="submit_recommendation",
                action_input={
                    "primary": "Schaeffler",
                    "backup": "NTN-SNR",
                    "rationale": "Best price within deadline, with faster backup option",
                },
                observation="Recommendation submitted and acknowledged by procurement manager.",
            ),
        ],
        final_answer="Recommend Schaeffler at 29,300 EUR total (21d lead). Backup: NTN-SNR.",
    )

    weak_trajectory = Trajectory(
        trajectory_id="sc-traj-weak",
        task_id="sc-001",
        steps=[
            TrajectoryStep(
                step_id=0,
                thought="Search for bearings",
                action="supplier_search",
                action_input={"product": "bearings"},
                observation="Found 200+ results for generic bearings worldwide",
            ),
            TrajectoryStep(
                step_id=1,
                thought="Just pick the first one",
                action="submit_recommendation",
                action_input={"primary": "BearingCo", "rationale": "first result"},
                observation="Recommendation submitted.",
            ),
        ],
        final_answer="Use BearingCo.",
    )

    client = OpenAIClient(
        model=os.environ.get("ADARUBRIC_MODEL", "gpt-4o"),
        base_url=os.environ.get("ADARUBRIC_BASE_URL"),
        api_key=os.environ.get("ADARUBRIC_API_KEY") or os.environ.get("OPENAI_API_KEY"),
    )

    pipeline = AdaRubricPipeline(
        generator=LLMRubricGenerator(client),
        evaluator=LLMTrajectoryEvaluator(
            client,
            aggregator=ConfidenceNormalizedAggregator(recency_decay=1.0),
        ),
        filter_=CompositeFilter([
            AbsoluteThresholdFilter(min_score=2.5),
            DimensionAwareFilter(default_threshold=2.0),
        ]),
    )

    rubric_path = _rubric_path_from_env()
    rubric = await load_or_generate_rubric(
        pipeline,
        task,
        rubric_path=rubric_path,
        num_dimensions=5,
    )

    eval_runs = _eval_runs_from_env()
    results: list[PipelineResult] = []
    for run_number in range(1, eval_runs + 1):
        print(f"Evaluation run {run_number}/{eval_runs}")
        result = await pipeline.run(
            task,
            [good_trajectory, weak_trajectory],
            rubric=rubric,
        )
        results.append(result)

    report = build_report(results, rubric_path=rubric_path)
    report_path = _report_path_from_env()
    save_report(report, report_path)
    print(report)
    print(f"\nSaved report to {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
