"""Generate initial rubrics for the Jiawen mobile-GUI task.

This script is intentionally separate from ``supply_chain_eval.py`` so rubric
generation can be studied without immediately evaluating the same trajectories.

The default prompt uses task information plus observable environment evidence.
It does not treat the observed rank-1 title as a fixed answer, because the
ranking can change over time. Optional calibration contrast can be enabled with
environment variables, but it is off by default to avoid overfitting.

PowerShell example:
    $env:ADARUBRIC_BASE_URL="http://localhost:8000/v1"
    $env:ADARUBRIC_API_KEY="EMPTY"
    $env:ADARUBRIC_MODEL="your-local-model-name"
    .venv\\Scripts\\python examples\\generate-jiawen-rubrics.py

Optional settings:
    ADARUBRIC_JIAWEN_WORKBOOK
    ADARUBRIC_RUBRIC_PATH
    ADARUBRIC_EVIDENCE_PATH
    ADARUBRIC_RAW_RESPONSE_PATH
    ADARUBRIC_NUM_DIMENSIONS
    ADARUBRIC_TEMPERATURE
    ADARUBRIC_MAX_TOKENS
    ADARUBRIC_INCLUDE_FEW_SHOT
    ADARUBRIC_REPAIR_INVALID_JSON
    ADARUBRIC_VALIDATE_RUBRIC
    ADARUBRIC_VALIDATION_ATTEMPTS
    ADARUBRIC_INCLUDE_CALIBRATION_CONTRAST
    ADARUBRIC_CALIBRATION_TRAJECTORY_IDS
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from collections.abc import Iterable
from pathlib import Path

from pydantic import ValidationError

from adarubric import DynamicRubric, TaskDescription, Trajectory
from adarubric.core.exceptions import RubricGenerationError
from adarubric.generator.prompts import (
    RUBRIC_GENERATION_FEW_SHOT,
    RUBRIC_GENERATION_SYSTEM,
    RUBRIC_GENERATION_USER,
)
from adarubric.generator.validation import OpenAIEmbeddingProvider, RubricValidator
from adarubric.llm.json_extract import extract_json_substring
from adarubric.llm.openai_client import OpenAIClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
JIAWEN_DATASET_ROOT = PROJECT_ROOT / "jiawen-dataset"
DEFAULT_WORKBOOK = (
    JIAWEN_DATASET_ROOT
    / "outputs"
    / "gui_trajectories"
    / "mobile_gui_trajectories_qwen.xlsx"
)
DEFAULT_RUBRIC_PATH = PROJECT_ROOT / "docs" / "rubrics" / "jiawen_gui_initial_rubric.json"
DEFAULT_EVIDENCE_PATH = (
    PROJECT_ROOT / "docs" / "rubrics" / "jiawen_gui_initial_rubric.evidence.md"
)
DEFAULT_RAW_RESPONSE_PATH = (
    PROJECT_ROOT / "docs" / "rubrics" / "jiawen_gui_initial_rubric.raw_response.txt"
)

TITLE_PATTERN = re.compile(r"《([^》]+)》")

JIAWEN_SYSTEM_EXTENSION = """\
### Jiawen GUI Evidence Extension

When supplemental environment evidence is provided, use it only to identify
observable GUI states and completion boundaries. Do not hard-code volatile
observed content such as a currently ranked title; evaluate whether the agent
selects the current ranked target at evaluation time."""

JIAWEN_USER_EXTENSION = """\
### Supplemental Observable Environment Evidence

{environment_evidence}

### Optional Calibration Contrast

{calibration_contrast}

### Rubric Requirements For This Task

- The task target is the drama that is ranked first on the current TV-drama
  must-watch ranking page at evaluation time.
- The rubric may refer to "the current rank-1 drama" or "the target ranked
  drama", but it must not name a specific observed title.
- Distinguish complete playback progress from merely reaching the ranking page,
  merely identifying the rank-1 item, or stopping on a detail/ad/loading page.
- Include common mobile-GUI interruptions only when they affect completion:
  permission dialogs, advertising, loading states, identity verification, and
  premature termination.
- Return exactly {num_dimensions} dimensions."""

RUBRIC_JSON_CONTRACT = """\
You MUST return only one valid JSON object. Do not use markdown fences, comments,
or explanatory prose outside the JSON.

The JSON object must have this shape:
{{
  "task_id": "same task id as provided",
  "dimensions": [
    {{
      "name": "ConcisePascalCaseName",
      "description": "at least 10 characters",
      "weight": 0.2,
      "scoring_criteria": {{
        "1": "concrete behavior for score 1",
        "2": "concrete behavior for score 2",
        "3": "concrete behavior for score 3",
        "4": "concrete behavior for score 4",
        "5": "concrete behavior for score 5"
      }}
    }}
  ],
  "generation_rationale": "brief rationale"
}}

Rules:
- dimensions must contain exactly {num_dimensions} objects.
- dimension weights must sum to 1.0.
- scoring_criteria must contain exactly string keys "1", "2", "3", "4", "5".
- do not include any observed volatile title from the evidence."""

JSON_REPAIR_SYSTEM = """\
You repair malformed rubric outputs into valid JSON.
Return only one valid JSON object and preserve the intended rubric content.
Do not add markdown fences, comments, or explanatory prose."""


def _bool_env(name: str, *, default: bool) -> bool:
    configured = os.environ.get(name)
    if configured is None:
        return default
    return configured.strip().lower() in {"1", "true", "yes", "y", "on"}


def _int_env(name: str, *, default: int, minimum: int = 1) -> int:
    configured = os.environ.get(name)
    if configured is None:
        return default
    try:
        value = int(configured)
    except ValueError:
        raise ValueError(f"{name} must be an integer, got {configured!r}") from None
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")
    return value


def _float_env(name: str, *, default: float) -> float:
    configured = os.environ.get(name)
    if configured is None:
        return default
    try:
        return float(configured)
    except ValueError:
        raise ValueError(f"{name} must be a float, got {configured!r}") from None


def _path_env(name: str, *, default: Path) -> Path:
    configured = os.environ.get(name)
    if not configured:
        return default
    path = Path(configured)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _load_jiawen_objects() -> tuple[TaskDescription, list[Trajectory], Path]:
    if not JIAWEN_DATASET_ROOT.exists():
        raise FileNotFoundError(f"Jiawen dataset directory not found: {JIAWEN_DATASET_ROOT}")

    dataset_path = str(JIAWEN_DATASET_ROOT)
    if dataset_path not in sys.path:
        sys.path.insert(0, dataset_path)

    try:
        from trajectory_tools.excel_to_object import load_objects
    except ModuleNotFoundError as exc:
        if exc.name == "openpyxl":
            raise RuntimeError(
                "jiawen-dataset requires openpyxl. Install it with: "
                ".venv\\Scripts\\python -m pip install openpyxl"
            ) from exc
        raise

    workbook_path = _path_env("ADARUBRIC_JIAWEN_WORKBOOK", default=DEFAULT_WORKBOOK)
    tasks_by_id, trajectories = load_objects(workbook_path=workbook_path)
    if not tasks_by_id:
        raise ValueError("jiawen-dataset returned no TaskDescription objects")

    task_id = os.environ.get("ADARUBRIC_TASK_ID")
    if task_id:
        if task_id not in tasks_by_id:
            available = ", ".join(sorted(tasks_by_id))
            raise ValueError(f"Unknown ADARUBRIC_TASK_ID={task_id!r}. Available: {available}")
        task = tasks_by_id[task_id]
    else:
        task = next(iter(tasks_by_id.values()))

    selected = [trajectory for trajectory in trajectories if trajectory.task_id == task.task_id]
    if not selected:
        raise ValueError(f"No trajectories found for task_id={task.task_id}")
    return task, selected, workbook_path


def _all_text(trajectory: Trajectory) -> str:
    parts: list[str] = []
    if trajectory.final_answer:
        parts.append(trajectory.final_answer)
    for step in trajectory.steps:
        if step.thought:
            parts.append(step.thought)
        parts.append(step.action)
        parts.append(step.observation)
    return "\n".join(parts)


def _extract_observed_titles(trajectories: Iterable[Trajectory]) -> set[str]:
    titles: set[str] = set()
    for trajectory in trajectories:
        for match in TITLE_PATTERN.finditer(_all_text(trajectory)):
            title = match.group(1).strip()
            if title:
                titles.add(title)
    return titles


def _contains_any(text: str, keywords: Iterable[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _summarize_environment(trajectories: list[Trajectory]) -> str:
    """Create aggregate UI evidence without exposing volatile show titles."""
    corpus = "\n".join(_all_text(trajectory) for trajectory in trajectories)

    signals = [
        (
            "Mobile home/app launch",
            _contains_any(corpus, ["手机主屏幕", "爱奇艺应用图标", "打开应用"]),
            "The agent can be observed launching the video app from the mobile home screen.",
        ),
        (
            "Video app home and TV-drama channel",
            _contains_any(corpus, ["首页", "电视剧频道", "电视剧标签", "电视剧"]),
            "The app home page exposes a TV-drama channel/tab that is relevant to the task.",
        ),
        (
            "Ranking page entry",
            _contains_any(corpus, ["风云榜", "热播榜", "排行榜"]),
            "The TV-drama area exposes ranking entry points such as hot/ranking pages.",
        ),
        (
            "Must-watch ranking tab",
            _contains_any(corpus, ["必看榜"]),
            (
                "The ranking page contains a must-watch tab; it must be selected "
                "rather than other ranking tabs."
            ),
        ),
        (
            "Current rank-1 item",
            _contains_any(corpus, ["排名第一", "排行第一", "榜No.1", "No.1"]),
            (
                "The target should be derived from the item currently shown as "
                "rank 1 on the must-watch ranking."
            ),
        ),
        (
            "Target detail/play page",
            _contains_any(corpus, ["详情页", "播放页面", "播放详情页", "选集", "第1集"]),
            (
                "After selecting the current rank-1 item, detail/play pages can "
                "show title, ranking tag, episode selection, and player/ad area."
            ),
        ),
        (
            "Completion blockers",
            _contains_any(corpus, ["广告", "弹窗", "身份核实", "加载", "阻塞", "未开始播放"]),
            (
                "Common completion blockers include ads, permission dialogs, "
                "loading states, and identity verification."
            ),
        ),
    ]

    lines = [
        "The following evidence is aggregated from stable screenshot observations.",
        "It describes reusable UI states, not fixed answers.",
        "",
        "Observed UI signals:",
    ]
    for name, present, description in signals:
        status = "observed" if present else "not observed"
        lines.append(f"- {name}: {status}. {description}")

    lines.extend(
        [
            "",
            "Important anti-overfitting note:",
            "- Any title observed in the collected trajectories is temporary ranking content.",
            (
                "- The rubric must evaluate selection of the current rank-1 TV drama, "
                "not a fixed show name."
            ),
            (
                "- Do not include exact coordinates, trajectory IDs, step counts, or "
                "observed show titles in dimension names or scoring criteria."
            ),
        ]
    )
    return "\n".join(lines)


def _completion_pattern(trajectory: Trajectory) -> str:
    text = _all_text(trajectory)
    if _contains_any(text, ["仅停留在榜单", "未执行点击播放", "未开始播放"]):
        return (
            "partial: reaches the correct ranking context but stops before "
            "initiating target playback"
        )
    if _contains_any(text, ["身份核实", "验证", "阻塞", "未观察到视频正片"]):
        return (
            "blocked: reaches the target context but does not show clear playback "
            "completion because of interruption or blocking states"
        )
    if _contains_any(text, ["播放广告", "播放页面", "详情或播放页面", "第1集", "选集"]):
        return (
            "near-complete: selects the current rank-1 item and reaches a target "
            "detail/playback context"
        )
    return "unknown: useful trajectory evidence exists, but the completion boundary is ambiguous"


def _calibration_trajectories(trajectories: list[Trajectory]) -> list[Trajectory]:
    configured = os.environ.get("ADARUBRIC_CALIBRATION_TRAJECTORY_IDS", "").strip()
    if not configured:
        return []

    requested = {item.strip() for item in configured.split(",") if item.strip()}
    selected = [
        trajectory
        for trajectory in trajectories
        if trajectory.trajectory_id in requested
        or str(trajectory.metadata.get("source_session_id", "")) in requested
    ]
    missing = requested - {
        trajectory.trajectory_id for trajectory in selected
    } - {str(trajectory.metadata.get("source_session_id", "")) for trajectory in selected}
    if missing:
        raise ValueError(f"Unknown calibration trajectory id(s): {sorted(missing)}")
    return selected


def _summarize_calibration_contrast(trajectories: list[Trajectory]) -> str:
    if not _bool_env("ADARUBRIC_INCLUDE_CALIBRATION_CONTRAST", default=False):
        return (
            "No calibration trajectories are provided by default. Generate the "
            "initial rubric from the task and reusable environment evidence only."
        )

    selected = _calibration_trajectories(trajectories)
    if not selected:
        return (
            "Calibration contrast was requested, but no explicit "
            "ADARUBRIC_CALIBRATION_TRAJECTORY_IDS were provided. Do not infer "
            "labels from all trajectories."
        )

    lines = [
        "Use these examples only to understand completion boundaries.",
        "Do not copy their IDs, coordinates, step counts, or observed titles into the rubric.",
        "",
    ]
    for index, trajectory in enumerate(selected, 1):
        lines.append(f"- Calibration example {index}: {_completion_pattern(trajectory)}.")
    return "\n".join(lines)


def build_messages(
    task: TaskDescription,
    trajectories: list[Trajectory],
    *,
    num_dimensions: int,
) -> list[dict[str, str]]:
    environment_evidence = _summarize_environment(trajectories)
    calibration_contrast = _summarize_calibration_contrast(trajectories)
    system_content = RUBRIC_GENERATION_SYSTEM.format(num_dimensions=num_dimensions)
    if _bool_env("ADARUBRIC_INCLUDE_FEW_SHOT", default=False):
        system_content += "\n\n" + RUBRIC_GENERATION_FEW_SHOT
    system_content += "\n\n" + JIAWEN_SYSTEM_EXTENSION

    base_user_content = RUBRIC_GENERATION_USER.format(
        task_id=task.task_id,
        instruction=task.instruction,
        domain=task.domain or "General",
        complexity=task.complexity.value,
        expected_tools=", ".join(task.expected_tools) if task.expected_tools else "Not specified",
        context=json.dumps(task.context, ensure_ascii=False) if task.context else "None",
    )
    final_instruction = "Generate the evaluation rubric now."
    if base_user_content.endswith(final_instruction):
        base_user_content = base_user_content[: -len(final_instruction)].rstrip()

    user_content = base_user_content + "\n\n" + JIAWEN_USER_EXTENSION.format(
        environment_evidence=environment_evidence,
        calibration_contrast=calibration_contrast,
        num_dimensions=num_dimensions,
    )
    user_content += (
        "\n\n"
        + RUBRIC_JSON_CONTRACT.format(num_dimensions=num_dimensions)
        + "\n\nGenerate the evaluation rubric now."
    )

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


def _evidence_from_messages(messages: list[dict[str, str]], workbook_path: Path) -> str:
    lines = [
        "# Jiawen GUI Initial Rubric Generation Evidence",
        "",
        f"- Workbook: `{workbook_path}`",
        f"- Model: `{os.environ.get('ADARUBRIC_MODEL', 'gpt-4o')}`",
        f"- AdaRubric few-shot enabled: `{_bool_env('ADARUBRIC_INCLUDE_FEW_SHOT', default=False)}`",
        (
            "- Calibration contrast enabled: "
            f"`{_bool_env('ADARUBRIC_INCLUDE_CALIBRATION_CONTRAST', default=False)}`"
        ),
        "",
    ]
    for message in messages:
        lines.append(f"## {message['role'].title()} Prompt")
        lines.append("")
        lines.append(message["content"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _write_raw_response(path: Path, *, stage: str, raw: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"## {stage}\n\n{raw.rstrip()}\n", encoding="utf-8")


def _rubric_text(rubric: DynamicRubric) -> str:
    return rubric.model_dump_json(indent=2)


def _find_forbidden_title_usage(rubric: DynamicRubric, titles: set[str]) -> list[str]:
    if not titles:
        return []
    rubric_json = _rubric_text(rubric)
    return sorted(title for title in titles if title and title in rubric_json)


def _correct_task_id(rubric: DynamicRubric, task: TaskDescription) -> DynamicRubric:
    if rubric.task_id == task.task_id:
        return rubric
    return rubric.model_copy(update={"task_id": task.task_id})


def _parse_rubric_json(raw: str) -> DynamicRubric:
    extracted = extract_json_substring(raw)
    return DynamicRubric.model_validate_json(extracted)


async def _repair_rubric_json(
    client: OpenAIClient,
    *,
    raw: str,
    task: TaskDescription,
    num_dimensions: int,
    max_tokens: int,
    raw_response_path: Path,
) -> DynamicRubric:
    repair_messages = [
        {"role": "system", "content": JSON_REPAIR_SYSTEM},
        {
            "role": "user",
            "content": (
                RUBRIC_JSON_CONTRACT.format(num_dimensions=num_dimensions)
                + "\n\nThe task_id must be: "
                + task.task_id
                + "\n\nMalformed rubric output to repair:\n"
                + raw
            ),
        },
    ]
    repaired = await client.generate_text(
        repair_messages,
        temperature=0.0,
        max_tokens=max_tokens,
    )
    _write_raw_response(raw_response_path, stage="json_repair_raw_response", raw=repaired)
    return _parse_rubric_json(repaired)


async def _generate_rubric_json(
    client: OpenAIClient,
    *,
    messages: list[dict[str, str]],
    task: TaskDescription,
    num_dimensions: int,
    temperature: float,
    max_tokens: int,
    raw_response_path: Path,
) -> DynamicRubric:
    raw = await client.generate_text(
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    _write_raw_response(raw_response_path, stage="rubric_raw_response", raw=raw)

    try:
        return _parse_rubric_json(raw)
    except (ValidationError, json.JSONDecodeError, ValueError):
        if not _bool_env("ADARUBRIC_REPAIR_INVALID_JSON", default=True):
            raise
        return await _repair_rubric_json(
            client,
            raw=raw,
            task=task,
            num_dimensions=num_dimensions,
            max_tokens=max_tokens,
            raw_response_path=raw_response_path,
        )


def build_validator() -> RubricValidator | None:
    if not _bool_env("ADARUBRIC_VALIDATE_RUBRIC", default=True):
        return None

    embedding_api_key = (
        os.environ.get("ADARUBRIC_EMBEDDING_API_KEY")
        or os.environ.get("ADARUBRIC_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or "EMPTY"
    )
    return RubricValidator(
        OpenAIEmbeddingProvider(
            model=os.environ.get("ADARUBRIC_EMBEDDING_MODEL", "text-embedding-3-small"),
            base_url=os.environ.get("ADARUBRIC_EMBEDDING_BASE_URL"),
            api_key=embedding_api_key,
        )
    )


async def generate_rubric(
    *,
    task: TaskDescription,
    trajectories: list[Trajectory],
    messages: list[dict[str, str]],
    num_dimensions: int,
) -> DynamicRubric:
    client = OpenAIClient(
        model=os.environ.get("ADARUBRIC_MODEL", "gpt-4o"),
        base_url=os.environ.get("ADARUBRIC_BASE_URL"),
        api_key=os.environ.get("ADARUBRIC_API_KEY") or os.environ.get("OPENAI_API_KEY") or "EMPTY",
    )
    validator = build_validator()
    attempts = _int_env("ADARUBRIC_VALIDATION_ATTEMPTS", default=10)
    temperature = _float_env("ADARUBRIC_TEMPERATURE", default=0.0)
    max_tokens = _int_env("ADARUBRIC_MAX_TOKENS", default=4096)
    raw_response_path = _path_env("ADARUBRIC_RAW_RESPONSE_PATH", default=DEFAULT_RAW_RESPONSE_PATH)
    observed_titles = _extract_observed_titles(trajectories)
    last_error = ""

    try:
        for attempt in range(1, attempts + 1):
            print(f"Generating Jiawen rubric attempt {attempt}/{attempts}")
            try:
                rubric = await _generate_rubric_json(
                    client,
                    messages=messages,
                    task=task,
                    num_dimensions=num_dimensions,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    raw_response_path=raw_response_path,
                )
            except Exception as exc:
                last_error = f"invalid JSON rubric output: {exc}"
                print(f"Rejected rubric: {last_error}")
                continue

            rubric = _correct_task_id(rubric, task)

            if len(rubric.dimensions) != num_dimensions:
                last_error = (
                    f"expected exactly {num_dimensions} dimensions, "
                    f"got {len(rubric.dimensions)}"
                )
                print(f"Rejected rubric: {last_error}")
                continue

            forbidden_titles = _find_forbidden_title_usage(rubric, observed_titles)
            if forbidden_titles:
                last_error = (
                    "rubric hard-coded volatile observed title(s): "
                    + ", ".join(forbidden_titles)
                )
                print(f"Rejected rubric: {last_error}")
                continue

            if validator is not None:
                validation = await validator.validate(rubric, task)
                if not validation.valid:
                    last_error = validation.summary()
                    print(f"Rejected rubric by validation: {last_error}")
                    continue

            return rubric

        raise RubricGenerationError(
            f"Failed to generate a valid Jiawen rubric after {attempts} attempt(s)",
            context={"last_error": last_error, "raw_response_path": str(raw_response_path)},
        )
    finally:
        await client.close()


async def main() -> None:
    task, trajectories, workbook_path = _load_jiawen_objects()
    num_dimensions = _int_env("ADARUBRIC_NUM_DIMENSIONS", default=5, minimum=1)
    rubric_path = _path_env("ADARUBRIC_RUBRIC_PATH", default=DEFAULT_RUBRIC_PATH)
    evidence_path = _path_env("ADARUBRIC_EVIDENCE_PATH", default=DEFAULT_EVIDENCE_PATH)

    messages = build_messages(task, trajectories, num_dimensions=num_dimensions)
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(_evidence_from_messages(messages, workbook_path), encoding="utf-8")

    rubric = await generate_rubric(
        task=task,
        trajectories=trajectories,
        messages=messages,
        num_dimensions=num_dimensions,
    )

    rubric_path.parent.mkdir(parents=True, exist_ok=True)
    rubric_path.write_text(_rubric_text(rubric) + "\n", encoding="utf-8")

    print(f"Loaded task {task.task_id} with {len(trajectories)} trajectories")
    print(f"Saved generation evidence to {evidence_path}")
    print(f"Saved rubric to {rubric_path}")
    print("Dimensions:")
    for dimension in rubric.dimensions:
        print(f"- [{dimension.weight:.2f}] {dimension.name}: {dimension.description}")


if __name__ == "__main__":
    asyncio.run(main())
