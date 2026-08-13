# 今日工作总结

今天主要围绕 Jiawen GUI 轨迹评估中的稳定性和对比实验设计继续推进。首先，在实际运行中发现一个关键问题：如果把长轨迹一次性塞进 evaluator，本地模型服务容易出现 502 error；但如果简单地按固定 step 数切 chunk，又会带来 chunk 边界上下文断裂的问题。尤其在 GUI 任务里，某个点击动作是否合理常常依赖前一个屏幕状态，如果边界刚好切在两个相关步骤之间，judge 可能无法正确理解动作含义。

针对这个问题，今天把 Jiawen evaluator 的 chunk 机制改成了带 overlap 的版本。当前设置为 5 个 step 作为一个核心 chunk，同时相邻 chunk 之间保留 1 个 step 的上下文重叠。重叠部分只给 judge 作为上下文参考，最终聚合时只保留每个 chunk 的 core steps 评分，不会重复计分。这样既能降低单次请求长度，缓解 502，又能减少边界处信息断裂带来的误判。

同时，为了避免实验结果被旧 checkpoint 污染，今天还给 JSONL 断点续跑机制加入了评估配置签名。现在每条评估结果都会记录当前的 evaluation settings，包括 chunk 是否开启、chunk size、overlap、max tokens、filter 和 aggregator 等。如果后续切换了 full-trajectory、普通 chunk 或 overlap chunk，脚本不会误复用旧 JSONL 里的结果，而会根据新的配置重新评估。这解决了“改了评估策略但续跑时沿用旧结果”的隐性风险。

今天还补充了一个新的对比实验：Baseline A，纯 Direct Judge。这个 baseline 不使用 rubrics，也不使用人工 GT 或人工排序原因，而是只把 Task 和候选轨迹中的 Action、Action Input、新 Observation 给大模型，让它直接把多条轨迹从优到劣排序并给出原因。这个实验的目的，是验证“复杂 rubric evaluator 是否真的优于直接 LLM-as-a-Judge 排序”，也可以帮助判断当前问题到底来自 rubric 设计、step-level 打分机制，还是模型本身的排序能力。

在设计 Direct Judge baseline 时，也明确控制了可见信息：judge 不会看到 thought，不会看到 final_answer，不会看到 rubrics，也不会看到 GT 或人工排序原因。这样可以保证 baseline 更干净，只基于任务目标和可观察执行过程进行判断。虽然 Direct Judge 会同时看到多条轨迹，但它只需要输出排序和简短理由，不需要像 AdaRubric evaluator 那样输出每个 step、每个 dimension 的详细 JSON 分数，因此输出压力更小，理论上可能比 step-level rubric 打分更稳定。

最后，今天进一步明确了当前评估体系暴露出的核心问题和下一步方向。现有 AdaRubric evaluator 的优势在于可以产生细粒度评分，但它容易受到长轨迹输出长度、chunk 边界、以及 pass/fail 绝对阈值不稳定的影响。拟解决方案是保留 overlap chunk 来保证可运行性，同时引入 Direct Judge baseline 做横向对比；后续还计划把“任务是否完成”从普通 rubric 维度中拆出来，作为 Completion Hard Gate，用完成状态决定大层级，再用 rubric score 或 direct judge score 做层级内部排序。
