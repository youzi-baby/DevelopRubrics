"""Tests for the Jiawen direct-judge baseline prompt switches."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from adarubric import TaskDescription, Trajectory, TrajectoryStep
from adarubric.core.models import TaskComplexity

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "examples" / "direct-judge-jiawen-baseline.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("direct_judge_jiawen_baseline", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["direct_judge_jiawen_baseline"] = module
    spec.loader.exec_module(module)
    return module


def _task() -> TaskDescription:
    return TaskDescription(
        task_id="task-1",
        instruction="Delete completed playback records.",
        complexity=TaskComplexity.MODERATE,
    )


def _trajectory() -> Trajectory:
    return Trajectory(
        trajectory_id="traj-1",
        task_id="task-1",
        steps=[
            TrajectoryStep(
                step_id=1,
                action="tap",
                action_input={"target": "history"},
                observation="The playback history page is visible.",
            )
        ],
    )


def test_completion_first_prompt_is_off_by_default():
    module = _load_module()

    messages = module.build_messages(_task(), [_trajectory()], config={})

    assert "Completion of the requested task is the most important criterion" not in messages[0][
        "content"
    ]


def test_completion_first_prompt_can_be_enabled():
    module = _load_module()

    messages = module.build_messages(
        _task(),
        [_trajectory()],
        config={"direct_judge_completion_first": True},
    )

    assert "Completion of the requested task is the most important criterion" in messages[0][
        "content"
    ]
