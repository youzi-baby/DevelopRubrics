# TrajectoryEvaluation Template

Use this template to document how a task-specific `DynamicRubric` is applied to
an agent `Trajectory`.

## Evaluation Purpose

The purpose of trajectory evaluation is to use a task-specific `DynamicRubric`
to judge how well an agent's execution trajectory satisfies the original task.

A trajectory is evaluated step by step. Each step is compared against the rubric
dimensions generated for the task. For every relevant dimension, the evaluator
assigns a score, confidence, and rationale. These step-level judgments are then
aggregated into per-dimension global scores and an overall trajectory score.

The evaluator should not create new rubric dimensions during scoring. It should
only use the existing `DynamicRubric`, including each dimension's `name`,
`description`, `weight`, and `scoring_criteria`.

## Structure

```mermaid
classDiagram
    class TrajectoryEvaluation {
        string trajectory_id
        string task_id
        DynamicRubric rubric_used
        StepEvaluation[] step_evaluations
        dict dimension_global_scores
        float global_score
        bool passed_threshold
        dict metadata
    }

    class StepEvaluation {
        int step_id
        DimensionScore[] dimension_scores
        string step_quality_summary
    }

    class DimensionScore {
        string dimension_name
        int score
        float confidence
        string rationale
    }

    class DynamicRubric {
        string task_id
        EvalDimension[] dimensions
        string generation_rationale
    }

    TrajectoryEvaluation "1" --> "1" DynamicRubric
    TrajectoryEvaluation "1" --> "1..*" StepEvaluation
    StepEvaluation "1" --> "0..*" DimensionScore
```

## Evaluation Questions

| Question | Meaning |
|---|---|
| Did the agent follow the task requirements? | Check whether the trajectory aligns with the original `TaskDescription`. |
| Did the agent perform well on each rubric dimension? | Score the trajectory against task-specific dimensions from `DynamicRubric`. |
| Where did the trajectory succeed or fail? | Use step-level scores and rationales to locate strong and weak steps. |
| Is this trajectory useful downstream? | Use global and dimension scores for filtering, reward assignment, or DPO pair generation. |

## Field Guide

| Field | Meaning | Notes |
|---|---|---|
| `trajectory_id` | The evaluated trajectory. | Should match `Trajectory.trajectory_id`. |
| `task_id` | The task this trajectory belongs to. | Should match `TaskDescription.task_id`. |
| `rubric_used` | The rubric used for evaluation. | Should be the generated or prebuilt `DynamicRubric`. |
| `step_evaluations` | Step-by-step evaluation results. | One entry per evaluated trajectory step. |
| `dimension_global_scores` | Final score for each rubric dimension. | Computed by the aggregation strategy. |
| `global_score` | Overall trajectory score. | Range is 0 to 5 in this project. |
| `passed_threshold` | Whether the trajectory passed filtering. | Set after a filter is applied. |
| `metadata` | Optional extra information. | Useful for model name, run id, timestamp, or source dataset. |

## Scoring Rules

| Field | Meaning | Notes |
|---|---|---|
| `dimension_name` | Rubric dimension being scored. | Must match a dimension name in `rubric_used`. |
| `score` | Step-level score for that dimension. | Integer from 1 to 5. |
| `confidence` | Evaluator confidence in the score. | Float from 0.0 to 1.0. |
| `rationale` | Explanation for the score. | Should cite observable trajectory behavior. |
| `step_quality_summary` | Short summary of the step. | Explains the overall quality of this step. |

## Evaluation Workflow

```mermaid
flowchart TD
    A[TaskDescription] --> B[DynamicRubric]
    C[Trajectory] --> D[Step-by-step Evaluation]
    B --> D
    D --> E[DimensionScore per step]
    E --> F[StepEvaluation]
    F --> G[Aggregation Strategy]
    G --> H[dimension_global_scores]
    G --> I[global_score]
    H --> J[TrajectoryFilter]
    I --> J
    J --> K[passed_threshold]
```

## Evaluation Metadata

| Field | Value |
|---|---|
| `task_id` |  |
| `trajectory_id` |  |
| `rubric_source` | generated / manual / reused |
| `evaluator_model` |  |
| `aggregation_strategy` | weighted_mean / geometric_mean / min_score |
| `filter_strategy` | absolute / percentile / dimension_aware / composite |

## Step Evaluations

### Step 0

#### Trajectory Step

| Field | Value |
|---|---|
| `thought` |  |
| `action` |  |
| `action_input` |  |
| `observation` |  |

#### Dimension Scores

| Dimension Name | Score | Confidence | Rationale |
|---|---:|---:|---|
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |

#### Step Quality Summary


### Step 1

#### Trajectory Step

| Field | Value |
|---|---|
| `thought` |  |
| `action` |  |
| `action_input` |  |
| `observation` |  |

#### Dimension Scores

| Dimension Name | Score | Confidence | Rationale |
|---|---:|---:|---|
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |

#### Step Quality Summary


### Step 2

#### Trajectory Step

| Field | Value |
|---|---|
| `thought` |  |
| `action` |  |
| `action_input` |  |
| `observation` |  |

#### Dimension Scores

| Dimension Name | Score | Confidence | Rationale |
|---|---:|---:|---|
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |

#### Step Quality Summary


## Aggregated Scores

### Per-Dimension Global Scores

| Dimension Name | Global Score |
|---|---:|
|  |  |
|  |  |
|  |  |
|  |  |
|  |  |

### Overall Result

| Field | Value |
|---|---|
| `global_score` |  |
| `passed_threshold` | true / false |

## JSON Shape

Use this shape when converting the evaluation into a `TrajectoryEvaluation`
object.

```json
{
  "trajectory_id": "",
  "task_id": "",
  "rubric_used": {
    "task_id": "",
    "dimensions": [],
    "generation_rationale": ""
  },
  "step_evaluations": [
    {
      "step_id": 0,
      "dimension_scores": [
        {
          "dimension_name": "",
          "score": 3,
          "confidence": 1.0,
          "rationale": ""
        }
      ],
      "step_quality_summary": ""
    }
  ],
  "dimension_global_scores": {},
  "global_score": 0.0,
  "passed_threshold": false,
  "metadata": {}
}
```
