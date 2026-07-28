# AdaRubric 方法风险与开放问题

这份文档整理当前 AdaRubric 项目设计中暴露出来的几个方法论风险。目的不是否定这个方法，而是在把它用于轨迹评估、数据过滤、reward learning 或 DPO 数据构造之前，先把关键假设和潜在问题讲清楚。

## 1. 同一个任务多次生成 Rubric 会发生漂移

### 问题

当前 pipeline 可以在每次评估任务时重新生成一个 `DynamicRubric`：

```text
TaskDescription
  -> generate_rubric(task)
  -> DynamicRubric
  -> evaluate trajectories
```

即使面对同一个 `TaskDescription`，多次调用 LLM 也可能生成不同的 rubric。即便 `temperature=0`，也不能保证输出完全一致，因为模型服务、结构化输出实现、后端版本、推理细节都可能带来差异。

### 为什么重要

如果 rubric 变了，评价标准也就变了。

这会带来几个风险：

| 风险 | 后果 |
|---|---|
| 分数不稳定 | 同一条 trajectory 在不同 rubric 下可能得到不同分数。 |
| 排名不稳定 | A 轨迹在一个 rubric 下优于 B，但换一个 rubric 后可能反过来。 |
| 比较不公平 | 不同轨迹如果用不同标准评估，结果不再可比。 |
| DPO 噪声 | chosen/rejected pair 可能反映的是 rubric 差异，而不是真实轨迹质量差异。 |
| reward 漂移 | reward learning 会在一个不断变化的目标上优化。 |
| 实验难复现 | 很难判断变化来自 agent、模型还是 rubric 本身。 |

### 当前项目行为

项目支持在 `pipeline.run(...)` 里传入已有 rubric：

```python
result = await pipeline.run(task, trajectories, rubric=rubric)
```

但如果不传 rubric，pipeline 会自动重新生成：

```python
if rubric is None:
    rubric = await self.generate_rubric(...)
```

也就是说，项目支持 rubric 复用，但默认没有强制做 rubric cache 或 rubric versioning。

### 后续发力方向

更可靠的做法应该是：先生成、筛选、保存一个 rubric，然后后续一直复用它。

```text
TaskDescription
  -> 生成多个候选 rubrics
  -> 选择最合适的 rubric
  -> 保存/cache 选中的 rubric
  -> 后续所有可比较轨迹都复用这个 rubric
```

至少应该记录这些信息：

| 记录项 | 目的 |
|---|---|
| `rubric_id` | 标识具体使用的是哪一版 rubric。 |
| `task_id` | 连接 rubric 和任务。 |
| `rubric_version` | 支持后续受控更新。 |
| `generation_model` | 记录生成 rubric 的模型。 |
| `generation_prompt_version` | 记录生成 rubric 使用的 prompt 版本。 |
| `created_at` | 支持复现和审计。 |

## 2. 项目缺少对 Rubric 质量的评估

### 问题

当前项目主要验证 rubric 的结构是否合法，但没有深入评估 rubric 的质量。

它会检查一些基础约束：

| 检查项 | 例子 |
|---|---|
| JSON/Pydantic 结构合法 | 输出能否解析成 `DynamicRubric`。 |
| scoring criteria 键完整 | 每个维度都有 1、2、3、4、5 分标准。 |
| 字段非空 | name、description 等字段满足基本长度约束。 |
| dimension name 不重复 | 各维度名称唯一。 |
| `task_id` 匹配 | rubric 对应正确任务。 |

这些检查是必要的，但不充分。

### 缺失的质量问题

项目目前没有回答：

| 质量问题 | 为什么重要 |
|---|---|
| rubric 是否和任务对齐？ | 结构合法的 rubric 也可能评估错方向。 |
| 是否覆盖关键失败模式？ | 缺少关键维度会让差轨迹通过。 |
| 维度是否能从 trajectory 中观察？ | 无法从轨迹判断的维度无法稳定评分。 |
| 维度是否相互独立？ | 重复维度会重复奖励同一种行为。 |
| 1 到 5 分标准是否清晰可区分？ | 模糊标准会增加评分噪声。 |
| 权重是否合理？ | 不合理权重会扭曲全局分数。 |
| rubric 是否产生稳定排名？ | 过滤、排序、DPO 都依赖稳定 ordering。 |
| rubric 是否接近人工判断？ | 高价值场景下需要和人类偏好一致。 |

### 后续发力方向

增加一个 `RubricSelector` 或 `RubricEvaluator` 阶段：

```text
TaskDescription
  -> 生成 K 个候选 rubrics
  -> 评估每个 rubric 的质量
  -> 选择最好的 rubric
  -> 保存选中的 rubric
  -> 用选中的 rubric 评估 trajectory
```

候选 rubric 可以从这些维度评分：

| 维度 | 含义 |
|---|---|
| Task Alignment | 是否直接反映任务要求。 |
| Coverage | 是否覆盖重要成功条件和失败模式。 |
| Observability | 每个维度是否能从 trajectory 证据中判断。 |
| Orthogonality | 各维度是否衡量不同方面。 |
| Criteria Clarity | 1 到 5 分标准是否具体、可区分。 |
| Calibration | 3 分是否表示合格，5 分是否表示优秀，1 分是否表示明显失败。 |
| Weight Reasonableness | 权重是否反映真实任务重要性。 |

这个阶段可以用 LLM 作为 meta-evaluator，也可以用人工审核、校准轨迹，或者三者结合。

## 3. 需要 Calibration Trajectories 校准 Rubric

### 问题

一个 rubric 单独看起来可能不错，但真正用于 trajectory 评估时不一定有效。

例如，一个不好的 rubric 可能会：

| 失败模式 | 例子 |
|---|---|
| 无法区分质量层级 | 好轨迹和弱轨迹得分接近。 |
| 过度奖励表面表达 | agent 写了很多 reasoning，但 action 是错的，仍然得高分。 |
| 低估关键失败 | 没有收集 quote，但最终回答写得漂亮，结果仍然过关。 |
| 排名不稳定 | prompt 或模型稍微变化，trajectory 排序就翻转。 |

### 后续发力方向

在正式使用 rubric 前，用一小组 calibration trajectories 测试它。

可以准备：

| 校准轨迹类型 | 目的 |
|---|---|
| 强轨迹 | 应该得到高分。 |
| 中等轨迹 | 应该得到中等分数。 |
| 弱轨迹 | 应该得到低分。 |
| 边界/特殊轨迹 | 测试 rubric 是否能捕捉微妙失败。 |

一个有用的 rubric 至少应该保持基本排序：

```text
strong > medium > weak
```

如果某个 rubric 连这个基本排序都做不到，就应该被修改或拒绝。

## 4. 固定 5 个维度不一定能迁移到所有任务域

### 问题

项目常用 `num_dimensions=5`。论文可能通过敏感性分析证明，在作者的任务分布上 5 个维度效果较好，但这不代表 5 对所有新任务域都是最优的。

代码中 5 是默认值：

```python
GeneratorConfig.num_dimensions = 5
LLMRubricGenerator.generate(..., num_dimensions=5)
```

项目允许修改这个值，但没有提供自动选择维度数量的机制。

### 为什么重要

合适的维度数量取决于任务复杂度和任务域。

| 维度数量 | 可能风险 |
|---|---|
| 太少 | 漏掉重要失败模式。 |
| 太多 | 维度冗余、评分噪声增加、成本升高、解释困难。 |
| 固定默认值 | 在一个 benchmark 上有效，不代表能迁移到另一个 domain。 |

例如：

| 任务类型 | 可能需要的维度数量 |
|---|---|
| 简单 QA | 2 到 3 个维度可能足够。 |
| 多步采购/API 编排 | 5 个维度可能合适。 |
| 安全关键工具调用 | 可能需要更多维度区分正确性、合规性、风险。 |
| 长链路 agent 任务 | 可能需要覆盖规划、工具使用、错误恢复、最终完成度等多个方面。 |

### 后续发力方向

对新的任务域做 dimension-count sensitivity analysis：

```text
num_dimensions = 3, 5, 7, 10
```

比较这些指标：

| 指标 | 含义 |
|---|---|
| Coverage | 是否覆盖任务关键要求。 |
| Redundancy | 维度之间是否重复。 |
| Score Stability | 同一轨迹分数是否稳定。 |
| Rank Consistency | 不同维度数量下 trajectory 排名是否一致。 |
| Human Agreement | 是否接近人工偏好或人工标注。 |
| Cost and Latency | 额外维度带来的 token 成本和时间是否值得。 |
| Interpretability | 人是否容易理解和审计这个 rubric。 |

最终最好按 task domain 设置推荐维度数，而不是全局固定为 5：

```yaml
domains:
  simple_qa:
    num_dimensions: 3
  procurement_api_orchestration:
    num_dimensions: 5
  safety_critical_agent:
    num_dimensions: 7
  long_horizon_tool_use:
    num_dimensions: 7
```

## 5. Prompt 质量是方法本身的重要组成部分

### 问题

rubric 生成和 trajectory 评估都高度依赖 system prompt 设计。

这个项目里，rubric 生成器并没有复杂算法去自动推导维度。真正的方法主要写在：

```text
adarubric/generator/prompts.py
adarubric/evaluator/prompts.py
```

### 为什么重要

prompt 变化会影响：

| 组件 | 影响 |
|---|---|
| 生成的 dimensions | rubric 衡量什么。 |
| scoring criteria | 每个分数等级的严格程度。 |
| evaluation behavior | 模型如何给每个 trajectory step 打分。 |
| rationales | 模型引用什么证据解释分数。 |
| downstream reward | agent 后续会被奖励学习什么行为。 |

因此，prompt version 应该像 model version 或 code version 一样被记录和管理。

### 后续发力方向

在 rubric 和 evaluation 输出中记录 prompt 元数据：

| 元数据 | 目的 |
|---|---|
| `generator_prompt_version` | 复现 rubric 生成过程。 |
| `evaluator_prompt_version` | 复现 trajectory 评分过程。 |
| `generation_model` | 记录生成 rubric 的模型。 |
| `evaluation_model` | 记录评估 trajectory 的模型。 |
| `temperature` | 记录采样设置。 |
| `max_tokens` | 记录输出预算。 |

## 总结

AdaRubric 的核心想法是有价值的：针对不同任务动态生成 rubric，并用它产生细粒度的 trajectory 评价和 reward 信号。但如果要可靠使用，还需要围绕 rubric 的稳定性和质量增加控制机制。

主要暴露的问题是：

| 风险 | 需要的控制 |
|---|---|
| Rubric drift | 对选中的 rubric 做缓存和版本管理。 |
| Rubric 质量未知 | 增加 rubric 评估和筛选。 |
| 缺少校准 | 用代表性 calibration trajectories 测试 rubric。 |
| 固定维度数量 | 对不同任务域做维度数量敏感性分析。 |
| Prompt 依赖强 | 对 generator/evaluator prompt 做版本化和审计。 |

更强的 pipeline 应该是：

```text
TaskDescription
  -> 生成候选 rubrics
  -> 评估/选择 rubric
  -> 缓存/版本化选中的 rubric
  -> 评估 trajectories
  -> 聚合分数
  -> 过滤数据或生成 reward 数据
```
