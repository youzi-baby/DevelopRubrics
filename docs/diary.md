# 工作总结

8 月 6 日主要围绕 Jiawen GUI 数据集接入 AdaRubric 流程展开。我们把原来偏单任务的 `supply_chain_eval.py` 思路扩展到了 Jiawen 自己的数据上，梳理了如何从 Excel 中加载 task 和 trajectories，并让 rubric generation 支持多任务场景。针对每个任务，脚本可以生成对应的 rubric、evidence 和 raw response，避免多个任务共用同一个输出文件造成覆盖。同时，我们讨论了 evidence 的边界：rubric 生成时不应该强拟合某一条具体轨迹，也不应该把容易变化的具体内容名称写死进 rubric，而应该抽象成任务目标、关键操作、完成条件和反过拟合约束。

同一天也搭建了专门的 Jiawen rubric 评估脚本，用生成好的 rubric 去给多任务、多轨迹进行评分。这个过程中明确了生成脚本和评估脚本的分工：`generate-jiawen-rubrics.py` 负责生成和保存 rubric，`evaluate-jiawen-rubrics.py` 负责加载已有 rubric 并评估轨迹。为了方便复查，评估输出被保存为 Markdown 汇总报告和 JSONL 明细文件；为了观察模型评分稳定性，也保留了多轮 evaluation runs 的均值、方差、最小值、最大值和 pass 次数统计。

8 月 7 日主要解决实际运行中遇到的稳定性问题。由于本地模型和 API 服务不够稳定，长轨迹一次性评估容易遇到 timeout、upstream error 或 JSON 截断。我们先实现了逐条 JSONL 落盘，让每条 trajectory 评估完成后马上写入结果，避免中途断掉后前面已经完成的评估全部丢失。随后又加入了自适应 chunk 机制：短轨迹保留完整上下文一次性评估，超过阈值的长轨迹自动按 step 分块评估，最后再合并 step-level evaluation 并重新聚合成整条轨迹的 global score。

今天还进一步加入了断点续跑能力。评估脚本启动时会读取已有的 `jiawen_gui_eval.jsonl`，根据 `task_id + run_number + trajectory_id` 判断哪些轨迹已经评估过；已有结果会直接复用并进入最终报告统计，缺失的轨迹才会继续调用模型评估。这样即使模型服务在中途崩掉，下次运行也能从断点附近继续，而不是从头重跑所有轨迹。

最后，我们基于验证集结果分析了当前 rubric evaluator 的效果。实验显示，模型在同一个任务内部的相对排序上有比较明显的信号，人工 pass 轨迹大多数时候能排在人工 fail 轨迹前面；但在绝对 pass/fail 判定上还没有校准好，尤其是一些失败轨迹会因为过程看起来合理而被打到较高分数。这个结果说明当前 rubric 更适合做完成质量排序，而如果要稳定地区分 pass/fail，还需要额外加强最终任务完成度判断，或者基于验证集重新校准阈值。
