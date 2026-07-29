# 今日工作总结

今天主要测试并分析了 AdaRubric 中 confidence-weighted aggregation 的问题，并基于实验结果新增了一种更合理的聚合方式。

## 做了什么

- 使用 `local_model_diagnostic.py` 对本地模型进行了评估能力测试。
- 对比了原始 `weighted_mean` 聚合方式和新加入的 `confidence_normalized` 聚合方式。
- 发现本地模型并不是完全无法区分好坏轨迹，而是原来的聚合公式会系统性压低好轨迹分数。
- 新增并接入了 `ConfidenceNormalizedAggregator`，让 confidence 同时进入分子和分母。
- 重新测试后，ideal 轨迹从原来的 `2.17` 提升到 `3.57`，而明显失败轨迹仍保持在 `1.00` 左右。

## 遇到的问题

原来的公式是：

```text
sum(score * confidence * step_weight) / sum(step_weight)
```

这个公式的问题是：`confidence` 只进入分子，没有进入分母。对于多步骤、多维度任务来说，很多 step 本来就只和部分维度相关。如果某个 step 与某个维度不相关，模型给了低 confidence，它仍然会占据分母中的 step weight，导致无关 step 也会把该维度分数拉低。

因此，即使是一条明显较好的轨迹，也可能因为多个低相关 step 被平均进来，最终得到偏低的全局分数。

## 给出的方案

新增的公式是：

```text
sum(score * confidence * step_weight) / sum(confidence * step_weight)
```

这样 confidence 被解释为 step 与 dimension 的相关性权重。低相关 step 不会再强行参与平均，也就不会异常压低相关维度的分数；而真正相关但表现差的 step，因为 confidence 高、score 低，仍然会被有效惩罚。

## 启发

这次实验说明，问题不一定出在本地模型本身，而可能出在评分聚合方式和 confidence 语义不匹配。对于复杂 agent trajectory 评估，confidence 更适合作为“证据相关性权重”，而不是单纯的分数折扣项。新的 `confidence_normalized` 聚合方式提升了好坏轨迹的区分度，同时没有把差轨迹一起抬高。
