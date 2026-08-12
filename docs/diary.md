# 今日工作总结

今天主要围绕 Jiawen GUI 轨迹评估流程继续完善，重点从“能跑通评估”推进到“评估结果是否可信、是否方便复现和分析”。首先检查了 `generate-jiawen-rubrics.py` 中 rubric 生成阶段能够看到的信息，确认默认情况下模型不会看到完整的逐步轨迹，但会基于所有 trajectory 的 observation 聚合出 environment evidence。因此，在更新 observation 描述为“前后截图差异”后，需要重新生成 rubrics，才能让新的观察信息影响后续评估标准。

在 evaluator 侧，今天明确了一个重要控制变量：评分模型不应该看到 trajectory 的 `thought`。原先 `LLMTrajectoryEvaluator` 会把 `thought / action / action_input / observation` 一起放进 prompt，这可能让 judge 受 agent 自我解释影响，而不是只基于可观察行为打分。为此，今天修改了 evaluator 的 prompt 构造逻辑，去掉了 `thought` 字段，并增加测试保证后续 prompt 中不会再泄漏 thought 文本。这样评估更接近“只看外显操作和环境反馈”的设定。

今天还新增了一个实验结果整理脚本 `examples/summarize-jiawen-eval.py`，用于读取 `jiawen_gui_eval.jsonl`，按 task 分组整理每条 trajectory 的分数、排序和 pass/fail 结果。这个脚本可以输出 Markdown 和 CSV，方便把模型评估结果与人工验证集结果进行对照分析。基于已有验证集结果，我们进一步观察到：当前 judge 在同一任务内部的相对排序能力较强，能较好地区分哪条轨迹更优；但绝对 pass/fail 边界仍然不稳定，存在失败轨迹被 rubric score 拉高并误判为 pass 的问题。

针对这个问题，今天形成了一个核心拟解决方案：把“任务是否完成”从普通 rubric 维度中拆出来，做成 Completion Hard Gate。也就是说，先由一个专门的 completion judge 判断轨迹是否真正完成任务；只有完成任务的轨迹才进入 pass 候选，rubric score 只用于完成轨迹内部的质量排序，以及未完成轨迹内部的失败程度排序。这样可以避免“过程看起来合理但最终没有完成”的轨迹因为多个 rubric 维度得分较高而被误判为成功。

同时，也讨论了 Completion Gate 本身可能出错的问题。它并不是绝对真值判断器，但相比把完成度、效率、操作合理性等混在一个加权平均分里，它的判断目标更单一，也更容易校准和解释。后续实现时应让 completion judge 保守判断：只有 observation 或 final state 明确显示任务目标已经达成，才判 completed=true；如果证据模糊、缺少关键完成条件，或者只是进入了相关页面但没有完成操作，都应判为 false。

今天还围绕长轨迹评估处理了 chunk 策略。由于去掉 thought 后 prompt 变短，默认策略重新切回完整 trajectory 一次性评估；但考虑到本地模型或 API 仍可能在长轨迹上报 timeout 或 JSON 截断，最终把 chunk 功能做成配置开关。默认 `evaluation_chunk_enabled=false`，也就是完整看全部 steps；如果后续运行中再次遇到长轨迹不稳定，只需要把配置改成 true，就可以启用按 step 分块评估并在最后重新聚合。

最后，今天还排查并解决了 GitHub 推送连接问题。问题并不是仓库或网络完全不可用，而是当前 PowerShell/Git 进程继承了错误的代理变量 `127.0.0.1:9`，而系统实际可用代理是 FlClash 的 `127.0.0.1:7890`。通过临时让 Git 走正确代理，成功恢复了 push 通道。这个问题也提醒后续如果再次遇到 GitHub 连接失败，需要优先检查当前进程的 `HTTP_PROXY / HTTPS_PROXY / ALL_PROXY` 是否与系统代理一致。
