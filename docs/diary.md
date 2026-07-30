# 今日工作总结

今天主要围绕 AdaRubric 在真实 GUI trajectory 数据上的接入和评估稳定性进行了实验与改造。前面已经完成了 supply-chain demo 的验证，今天进一步把 Jiawen 数据集中的 Excel 轨迹对象接入到 `supply_chain_eval.py` 中，使脚本可以直接从 `jiawen-dataset/trajectory_tools/excel_to_object.py` 加载我们自己的 `TaskDescription` 和 `Trajectory` 数据，而不是继续使用示例里的手写 good / weak 轨迹。

在改造过程中，保留了原来的 supply-chain demo 作为备用入口，同时让脚本默认检测并使用 `jiawen-dataset`。为了避免不同任务之间误用 rubric，也把 Jiawen 数据默认对应的 rubric 路径改成了 `docs/rubrics/jiawen_gui_rubric.json`。这样后续可以针对我们自己的 GUI 任务固定 rubric，然后反复运行 evaluator，观察同一 rubric 下模型评分是否稳定。

今天还继续完善了稳定性测试流程。脚本现在可以固定同一个 rubric，对同一批 trajectories 连续评估 10 次，并把每一轮结果以及均值、标准差、最大值、最小值、pass 次数等统计信息保存到报告文件中。这个设计可以帮助我们判断 evaluator 的波动范围，以及 good / bad trajectory 的排序和 pass/fail 结果是否稳定。

实际运行时遇到了一个本地模型服务相关的问题：在第 7 轮评估时出现了 `404 upstream error`。由于前面多轮已经成功完成，这个问题更像是本地模型服务或上游代理的偶发失败，而不是 rubric 或 evaluator 的逻辑错误。为此，进一步在脚本中加入了更适合本地模型的设置：默认将 trajectory evaluation 并发数降为 1，并为每一轮 evaluation 增加自动重试机制，减少实验被偶发服务错误中断的概率。

今天的主要启发是，真实数据接入后，评估系统的问题会从单纯的方法理解，转向更完整的工程稳定性问题。固定 rubric、重复评估、保存报告、控制并发、失败重试，这些机制对于判断一个 evaluator 是否可用非常重要。后续如果要系统比较不同模型或不同 rubric 的效果，需要继续保持 task、trajectory、rubric 和 evaluator 配置的可控性，避免把模型能力差异、rubric 差异和运行环境波动混在一起。
