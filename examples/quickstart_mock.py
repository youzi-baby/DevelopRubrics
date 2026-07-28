"""Quickstart without external LLM/API calls.

This example uses a deterministic mock LLM client so you can verify the
AdaRubric pipeline locally without an OpenAI API key or billing quota.

Usage:
    .venv\\Scripts\\python examples\\quickstart_mock.py
"""

from __future__ import annotations

import asyncio
from typing import TypeVar

from pydantic import BaseModel

from adarubric import (
    AdaRubricPipeline,
    DynamicRubric,
    EvalDimension,
    TaskDescription,
    Trajectory,
    TrajectoryStep,
)
from adarubric.evaluator.trajectory_evaluator import LLMTrajectoryEvaluator
from adarubric.filter.threshold import AbsoluteThresholdFilter
from adarubric.generator.llm_generator import LLMRubricGenerator
from adarubric.llm.base import LLMClient

T = TypeVar("T", bound=BaseModel)


class MockLLMClient(LLMClient):
    """Deterministic local stand-in for an LLM client."""

    async def generate_structured(
        self,
        messages: list[dict[str, str]],
        response_model: type[T],
        *,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> T:
        if response_model.__name__ == "DynamicRubric":
            return response_model.model_validate(
                DynamicRubric(
                    task_id="demo-001",
                    dimensions=[
                        EvalDimension(
                            name="ToolUseAccuracy",
                            description="Whether the agent uses the correct tools with suitable inputs.",
                            weight=1.2,
                            scoring_criteria={
                                1: "Incorrect or missing tool use.",
                                2: "Tool use is attempted but inputs are mostly wrong.",
                                3: "Tool use is basically correct with minor gaps.",
                                4: "Correct tools and mostly complete inputs.",
                                5: "Excellent tool choice, inputs, and sequencing.",
                            },
                        ),
                        EvalDimension(
                            name="ReasoningQuality",
                            description="Whether the agent's intermediate reasoning supports the task goal.",
                            weight=1.0,
                            scoring_criteria={
                                1: "Reasoning is absent or unrelated.",
                                2: "Reasoning is shallow or misses key constraints.",
                                3: "Reasoning is adequate but incomplete.",
                                4: "Reasoning is clear and task-aligned.",
                                5: "Reasoning is precise, complete, and anticipates edge cases.",
                            },
                        ),
                        EvalDimension(
                            name="FinalAnswerUsefulness",
                            description="Whether the final answer directly satisfies the user's request.",
                            weight=1.1,
                            scoring_criteria={
                                1: "No useful final answer.",
                                2: "Final answer is weak or incomplete.",
                                3: "Final answer mostly addresses the request.",
                                4: "Final answer is clear and useful.",
                                5: "Final answer is complete, clear, and well justified.",
                            },
                        ),
                    ],
                    generation_rationale="Mock rubric for local pipeline validation.",
                )
            )

        if response_model.__name__ == "_EvaluationResponse":
            return response_model.model_validate(
                {
                    "trajectory_id": "traj-demo-001",
                    "task_id": "demo-001",
                    "step_evaluations": [
                        {
                            "step_id": 0,
                            "dimension_scores": [
                                {
                                    "dimension_name": "ToolUseAccuracy",
                                    "score": 5,
                                    "confidence": 0.95,
                                    "rationale": "The weather tool is the right first step.",
                                },
                                {
                                    "dimension_name": "ReasoningQuality",
                                    "score": 4,
                                    "confidence": 0.9,
                                    "rationale": "The thought is clear and goal-directed.",
                                },
                            ],
                            "step_quality_summary": "Good weather lookup step.",
                        },
                        {
                            "step_id": 1,
                            "dimension_scores": [
                                {
                                    "dimension_name": "ToolUseAccuracy",
                                    "score": 4,
                                    "confidence": 0.9,
                                    "rationale": "The activity search follows from the rainy forecast.",
                                },
                                {
                                    "dimension_name": "ReasoningQuality",
                                    "score": 4,
                                    "confidence": 0.85,
                                    "rationale": "The agent correctly uses the forecast to choose indoor options.",
                                },
                            ],
                            "step_quality_summary": "Good follow-up activity search.",
                        },
                        {
                            "step_id": 2,
                            "dimension_scores": [
                                {
                                    "dimension_name": "ReasoningQuality",
                                    "score": 4,
                                    "confidence": 0.85,
                                    "rationale": "The final response is based on gathered evidence.",
                                },
                                {
                                    "dimension_name": "FinalAnswerUsefulness",
                                    "score": 5,
                                    "confidence": 0.95,
                                    "rationale": "The final answer states the forecast and gives useful options.",
                                },
                            ],
                            "step_quality_summary": "Strong final response.",
                        },
                    ],
                }
            )

        raise ValueError(f"No mock response configured for {response_model.__name__}")

    async def generate_text(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str:
        return "mock response"


async def main() -> None:
    task = TaskDescription(
        task_id="demo-001",
        instruction=(
            "Use the weather API to check if it will rain in Tokyo tomorrow, "
            "and if so, suggest indoor activities."
        ),
        domain="Personal Assistant",
        expected_tools=["weather_api", "activity_search"],
    )

    trajectory = Trajectory(
        trajectory_id="traj-demo-001",
        task_id="demo-001",
        steps=[
            TrajectoryStep(
                step_id=0,
                thought="I need to check tomorrow's weather in Tokyo first.",
                action="weather_api",
                action_input={"city": "Tokyo", "date": "tomorrow"},
                observation="Tomorrow: 70% chance of rain, high 18 C, low 12 C.",
            ),
            TrajectoryStep(
                step_id=1,
                thought="It's likely to rain. Let me find indoor activities in Tokyo.",
                action="activity_search",
                action_input={"city": "Tokyo", "type": "indoor", "limit": 5},
                observation=(
                    "1. TeamLab Borderless, 2. Tokyo National Museum, "
                    "3. Akihabara arcades, 4. Shibuya Sky observatory, "
                    "5. Cooking class in Tsukiji"
                ),
            ),
            TrajectoryStep(
                step_id=2,
                thought="I have good options. Let me compile a recommendation.",
                action="respond",
                action_input="compile recommendation",
                observation="Response delivered to user.",
            ),
        ],
        final_answer=(
            "It will likely rain in Tokyo tomorrow. Suggested indoor activities: "
            "TeamLab Borderless, Tokyo National Museum, Akihabara arcades, "
            "Shibuya Sky, and a Tsukiji cooking class."
        ),
    )

    mock_client = MockLLMClient()
    pipeline = AdaRubricPipeline(
        generator=LLMRubricGenerator(mock_client),
        evaluator=LLMTrajectoryEvaluator(mock_client),
        filter_=AbsoluteThresholdFilter(min_score=3.0),
    )

    result = await pipeline.run(task, [trajectory], num_dimensions=3)

    print("=== AdaRubric Mock Evaluation Results ===")
    print(f"Task: {task.instruction}")
    print(f"Rubric dimensions: {result.rubric.dimension_names}")
    print(f"Global score: {result.mean_score:.2f}/5.0")
    print(f"Survival rate: {result.survival_rate:.0%}")

    for ev in result.all_evaluations:
        print(f"\n--- Trajectory: {ev.trajectory_id} ---")
        print(f"  Global score: {ev.global_score:.2f}")
        for dim_name, dim_score in ev.dimension_global_scores.items():
            print(f"  {dim_name}: {dim_score:.2f}")
        for step_ev in ev.step_evaluations:
            print(f"  Step {step_ev.step_id}: {step_ev.step_quality_summary}")


if __name__ == "__main__":
    asyncio.run(main())
