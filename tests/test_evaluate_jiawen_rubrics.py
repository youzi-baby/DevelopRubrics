"""Tests for Jiawen evaluation script helpers."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from adarubric import Trajectory, TrajectoryStep

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "examples" / "evaluate-jiawen-rubrics.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("evaluate_jiawen_rubrics", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["evaluate_jiawen_rubrics"] = module
    spec.loader.exec_module(module)
    return module


def test_trajectory_for_evaluation_can_hide_action_and_action_input():
    module = _load_module()
    trajectory = Trajectory(
        trajectory_id="traj-1",
        task_id="task-1",
        steps=[
            TrajectoryStep(
                step_id=1,
                action='{"action":"click","coordinate":[384,483]}',
                action_input={"history": "Empty"},
                observation="The app opened.",
            )
        ],
    )

    prepared = module._trajectory_for_evaluation(
        trajectory,
        include_action=False,
        include_action_input=False,
    )

    assert prepared.steps[0].action == "Action hidden for this ablation."
    assert prepared.steps[0].action_input == {}
    assert prepared.steps[0].observation == "The app opened."
    assert "[384,483]" not in prepared.steps[0].action
    assert prepared.metadata["evaluation_include_action"] is False
    assert prepared.metadata["evaluation_include_action_input"] is False
