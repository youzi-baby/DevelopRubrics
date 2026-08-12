"""Prompt templates for trajectory evaluation."""

from __future__ import annotations

from typing import Any

EVALUATION_SYSTEM = """\
You are an expert evaluator of AI agent trajectories.

Given an agent's execution trajectory and a task-specific evaluation rubric,
produce a detailed, step-by-step evaluation.

### Evaluation Protocol

1. **Read the rubric carefully.** Internalize what each scoring level (1–5) means
   for every dimension.
2. **Evaluate each step independently.** For each (Thought, Action, Observation) step:
   - Score it on every applicable dimension using the rubric's criteria.
   - Assign a confidence (0.0–1.0) reflecting **step-dimension applicability**:
     how directly this step provides evidence for this rubric dimension.
     Confidence is NOT how certain you are that the step is good or bad.
     A clearly bad but dimension-relevant step should receive a low score with high
     confidence. A step that does not address the dimension should receive low
     confidence, even if the trajectory is generally poor.
     Use this calibration:
       * 0.0–0.2: not applicable; the step provides almost no evidence for this dimension.
       * 0.3–0.5: weakly applicable; only indirect or partial evidence is present.
       * 0.6–0.8: applicable; the step provides useful but incomplete evidence.
       * 0.9–1.0: directly applicable; the step clearly exercises this dimension.
   - Provide a concise rationale grounding the score in observed behavior.
3. **Be calibrated.** Score 3 = acceptable execution. Reserve 5 for genuinely excellent
   steps. Score 1 only for clearly broken behavior.
4. **Be specific.** Rationales must reference concrete actions or observations, not
   vague praise/criticism.

### Output Format

Return a JSON object with:
- trajectory_id: string
- task_id: string
- step_evaluations: array of objects, each containing:
  - step_id: integer
  - dimension_scores: array of objects, each containing:
    - dimension_name: string (must match a rubric dimension name exactly)
    - score: integer (1–5)
    - confidence: number (0.0–1.0)
    - rationale: string (1–2 sentences)
  - step_quality_summary: string (1 sentence overall assessment of the step)\
"""

EVALUATION_USER = """\
### Evaluation Rubric

{rubric_json}

### Agent Trajectory

**Task Instruction**: {instruction}

**Steps**:
{trajectory_text}

Evaluate this trajectory against the rubric now.\
"""


def format_trajectory_steps(steps: list[dict[str, Any]]) -> str:
    """Render trajectory steps as readable text for the LLM prompt."""
    parts: list[str] = []
    for step in steps:
        lines = [f"--- Step {step['step_id']} ---"]
        lines.append(f"**Action**: {step['action']}")
        if step.get("action_input"):
            lines.append(f"**Action Input**: {step['action_input']}")
        lines.append(f"**Observation**: {step['observation']}")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)
