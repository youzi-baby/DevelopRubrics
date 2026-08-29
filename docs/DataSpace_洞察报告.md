# DataSpace 论文洞察报告

论文：DataSpace: Benchmarking Data Agents for Verifiable Analytics over Heterogeneous Workspaces

研究视角：Agent 评测

## 核心观点

这篇论文的核心价值在于，它把 Data Agent 的评测对象从单点能力，例如 Text-to-SQL、文档问答、表格问答，提升到更接近真实工作流的“异构工作区求解”。在 DataSpace 中，Agent 拿到的不是整理好的数据库或指定文档，而是一个包含 CSV、JSON、SQLite、Markdown、PDF、视频等材料的 task-local workspace。Agent 必须自己判断证据在哪里、如何读取、如何跨文件对齐实体和字段，最后输出完整表格。

从 Agent 评测角度看，DataSpace 的关键不是“多模态”本身，而是它把多模态证据、工具使用、数据计算和最终答案物化放在同一个可验证闭环里。它不使用开放式报告或 LLM judge 作为主要评分方式，而是要求最终答案与 gold table 在语义上完全等价。因此，它更适合评估 Agent 是否能完成可交付的数据分析任务，而不仅是展示推理过程。

一个重要结论是：当前前沿模型在这类任务上仍然不稳定。最强模型 Grok 4.5 的 Task Accuracy 只有 66.34%，并且 76 个任务所有 6 个模型都失败。这说明 Data Agent 的瓶颈不只是模型知识或单次推理，而是 workspace discovery、跨模态 grounding、关系运算、输出 schema 控制等多个环节的组合可靠性。

建议配图：PDF 第 1 页 Figure 1，展示 DataSpace 的任务接口和跨 CSV、JSON、SQLite、PDF、视频的证据整合流程。

## 关键词

- Data Agent Evaluation
- Heterogeneous Workspace
- Verifiable Analytics
- Multimodal Evidence
- Cross-Language Benchmark
- Tool-Using Agent
- Complete Tabular Output
- Deterministic Evaluator
- Agent Harness
- Failure Attribution

## 业务启示

对企业级数据智能体来说，DataSpace 传递的第一个启示是：真实业务分析不是“给一个数据库，生成一条 SQL”这么简单。业务规则可能写在 PDF 报告里，字段解释可能散落在 Markdown 文档里，阈值可能在视频说明或会议材料里，交易、基金、病历等事实又可能在数据库或 CSV 文件里。因此，面向业务的数据 Agent 需要具备工作区级别的资料发现和整合能力。

第二个启示是，Agent 的输出交付能力必须被单独评测。论文的失败分析显示，很多失败不是因为 Agent 完全没有算出相关信息，而是最终提交的表格多列、少列、行粒度错误、排序不对或类型格式不合规。这对业务场景很关键：一个 Agent 即使中间分析接近正确，只要最后交付给用户的表不符合要求，业务上仍然不可用。

第三个启示是，Agent 产品不能只比较 foundation model，还要比较 harness。论文固定 MiMo-V2.5 后，不同 agent harness 的准确率从 30.98% 到 46.34%，差距达到 15.36 个百分点。也就是说，规划策略、上下文管理、工具接口、提交机制和自检流程，会显著影响同一个模型的最终表现。

## 背景介绍

现有相关 benchmark 可以大致分为三类。第一类是结构化数据评测，例如 Spider、BIRD、EHRSQL、BULL，主要检验自然语言到 SQL、数据库 schema 理解和关系查询能力。第二类是非结构化或多文档问答评测，例如 HotpotQA、CRAG、MMLongBench-Doc，主要检验检索、长文档理解和答案合成能力。第三类是更接近 Agent 的数据分析评测，例如 DABStep、KramaBench、LongDA、DataCross、FDABench，开始关注多步骤分析、多文件和多模态输入。

DataSpace 认为这些 benchmark 仍然没有同时解决三个问题。第一，workspace 范围不够完整，很多评测会预先给定数据库、表或文档，而真实 Agent 需要自己在工作区中发现证据。第二，输出契约不够统一，有的输出是事实短答，有的是代码、报告或开放式分析，不利于统一比较。第三，评测语义不够确定，有些任务依赖 rubric 或 LLM judge，而企业分析更需要可复现、可审计的结果比较。

DataSpace 因此把任务统一定义为：给定自然语言问题和异构工作区，Agent 输出完整的 typed table。所有任务都用同一个 deterministic evaluator 判断最终表格是否和 gold table 等价。

建议配图：PDF 第 4 页 Figure 2，展示 DataSpace-Builder 从 Text-to-SQL 数据源到异构 benchmark 的构造流程。

## 技术和创新点描述

DataSpace 的第一个创新是任务形态。它包含 410 个任务、7,439 个文件，总规模 15.01GB，覆盖 CSV、JSON、SQLite、Markdown、PDF 和视频。任务领域包括基金、股票、宏观经济和医疗分析，其中 64.6% 是跨语言任务，问题和工作区材料可能混合中文和英文。

论文 Table 2 给出的 benchmark 规模如下：

| 维度 | 数值 |
| --- | --- |
| 任务数 | 410 |
| 文件数 | 7,439 |
| 总存储规模 | 15.01GB |
| PDF | 1,088 个 PDF，25,384 页 |
| Markdown | 875 个文件，26.88M 字符 |
| 视频 | 189 个视频，总计 5.49 小时 |
| Reference answers | 126,409 行 |
| 最大答案表 | 12,962 行 |
| 需要保持行顺序的任务 | 92 |

建议截图：PDF 第 6 页 Table 2。

第二个创新是 DataSpace-Builder。它不是完全人工编写任务，而是从 EHRSQL 和 BULL 这类 Text-to-SQL 数据集出发，通过可执行 SQL 保留任务语义，再把结构化数据库转换成异构工作区。核心流程包括四步：

| 阶段 | 作用 | 对 Agent 评测的意义 |
| --- | --- | --- |
| Cross-Language Transformation | 联合转换问题、数据库和 SQL，保持实体、字段、谓词、单位、排序和时间范围一致 | 构造跨语言任务，同时避免问题和数据语义漂移 |
| Constraint-Aware Relational Sampling | 采样数据库，但保留过滤值、join 路径、外键闭包和目标实体 | 保证任务规模可控，同时仍然可解 |
| Modality Routing & Artifact Rendering | 把表渲染为 CSV、JSON、SQLite、Markdown、PDF，并为部分任务生成视频证据 | 把单一数据库查询变成异构 workspace 分析 |
| Human Review & Task Repair | 由专家盲解、核 gold、核 evaluation config，不一致则修复 | 降低自动构造 benchmark 的语义错误风险 |

第三个创新是 deterministic evaluator。它对最终 CSV 做精确评测，但又允许合理的等价表达：列名不参与评分，列顺序可以不同；数字按整数、小数位或有效数字精度归一化；百分号、日期、时间、布尔值、空值都有专门规则；如果任务要求 ranking 或顺序，则按行序列比较，否则按无序多重集合比较。这比直接字符串匹配更宽容，也比 LLM judge 更可复现。

建议配图：PDF 第 21 页 Figure 18，展示某个任务的 frozen evaluation configuration；也可截 PDF 第 21 页 Algorithm 8，展示表格结果评测流程。

## 效果总结

### 实验设置

论文评测全部 410 个任务，分成两组 controlled comparison。第一组固定 DataSpace-Agent 这个轻量 ReAct 风格 harness，只替换 backbone，比较不同模型能力。第二组固定 MiMo-V2.5 backbone，只替换 agent harness，比较不同框架对同一模型的影响。

每个任务给 Agent 完整 workspace 和问题。Backbone 对比中，每个任务限制 60 个 model turns、50 次 tool actions、1,800 秒，总资源为 4 CPUs 和 16GiB 内存。评分指标是 Task Accuracy：最终提交表格与参考表格语义等价则记 1，否则记 0；缺失预测、非法输出、运行失败和超时都算错。

### Backbone 对比

论文 Table 3 的主要结果如下：

| Backbone | 发布时间 | 正确数 / 410 | Task Accuracy |
| --- | --- | ---: | ---: |
| Grok 4.5 | 2026-07 | 272 | 66.34% |
| GPT-5.6 Sol | 2026-07 | 265 | 64.63% |
| Kimi K3 | 2026-07 | 219 | 53.41% |
| MiMo-V2.5 | 2026-04 | 161 | 39.27% |
| Claude Sonnet 5 | 2026-06 | 135 | 32.93% |
| MiniMax M3 | 2026-06 | 117 | 28.54% |

这个结果说明 DataSpace 对当前模型仍然有区分度。最强和最弱 backbone 相差 37.80 个百分点，但最强模型也只完成约三分之二任务。更有意思的是，6 个模型共同做对的任务只有 56 个，共同做错的任务有 76 个，而 oracle union 可以达到 81.46%，说明不同模型有互补成功案例，benchmark 中既存在共同难点，也存在模型特异性短板。

建议截图：PDF 第 7 页 Table 3。

### Harness 对比

固定 MiMo-V2.5 时，harness 对结果影响很明显：

| Harness | 版本 | 正确数 / 410 | Task Accuracy |
| --- | --- | ---: | ---: |
| Grok Build | v0.2.106 | 190 | 46.34% |
| Claude Code | v2.1.217 | 183 | 44.63% |
| DataSpace-Agent | Ours | 161 | 39.27% |
| Codex | v0.145.0 | 143 | 34.88% |
| Smolagents | v1.26.0 | 127 | 30.98% |

这组实验对 Agent 评测很重要。它说明评测对象不应只写成“某某大模型在 benchmark 上多少分”，因为 Agent 是模型、工具、上下文管理、动作空间、错误恢复和输出控制的组合系统。同一个 backbone 换 harness，准确率可以差 15.36 个百分点。

### 效率对比

论文还比较了 token、成本、动作数和延迟。GPT-5.6 Sol 比 Grok 4.5 只低 1.71 个百分点，但平均 token 少 74.2%，动作数少 50.3%，延迟少 39.2%。这说明在 Agent 评测里，accuracy 不是唯一维度，效率和稳定性也应进入评价体系。

| Backbone | Accuracy | 平均 Tokens | 成本 / 任务 | 平均 Actions | 平均延迟 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Grok 4.5 | 66.34% | 301.9K | $0.169 | 18.1 | 80.9s |
| GPT-5.6 Sol | 64.63% | 77.8K | $0.200 | 9.0 | 49.2s |
| Kimi K3 | 53.41% | 235.2K | $0.235 | 19.7 | 260.1s |
| MiMo-V2.5 | 39.27% | 237.9K | $0.011 | 19.2 | 90.9s |
| Claude Sonnet 5 | 32.93% | 440.4K | $0.224 | 19.3 | 128.9s |
| MiniMax M3 | 28.54% | 498.6K | $0.042 | 25.0 | 104.5s |

建议截图：PDF 第 7 页 Figure 5，展示 accuracy 与 token、成本、actions、latency 的权衡；补充可用 PDF 第 23 页 Table 11。

### 任务特征影响

Figure 6 和 Table 12 表明，最稳定的难点是多模态证据整合和 join。多模态任务相比单模态任务，在所有 backbone 上都下降，降幅为 1.8 到 14.0 个百分点；join 任务相比非 join 任务也在所有 backbone 上下降，降幅为 9.7 到 19.8 个百分点。

| 任务特征 | 主要观察 |
| --- | --- |
| Cross-language | 影响依赖模型；MiMo 和 Grok 下降，但 GPT 和 Claude 反而提升 |
| Multimodal evidence | 所有模型下降，是一致性难点 |
| Document evidence | 对 GPT 和 Kimi 影响接近中性，对其他模型下降明显 |
| Video evidence | 对 GPT 和 Kimi 有提升，对 MiMo、Claude、MiniMax 有下降 |
| Largest workspace | 最大 workspace quartile 对所有模型更难，但难度与文件大小不是单调关系 |
| Join | 所有模型明显下降，是最稳定的结构性瓶颈 |
| Aggregation | 影响不一致，有些模型反而更高 |
| Answer rows / columns / order | 不呈现单调负相关，说明难点不只是输出规模 |

这对设计 Agent 评测有启发：不能只按输入大小或答案行数衡量任务难度，更应该标注和分析证据组合方式、跨模态路径、join、grounding、normalization 等操作结构。

建议截图：PDF 第 8 页 Figure 6；也可补充 PDF 第 23 页 Table 12。

### 失败分析

论文对 Grok 4.5 的 136 个失败进行了 trace-level root-cause audit。结果显示，最大失败来源是 answer materialization，而不是 evidence discovery。

| 失败阶段 | 含义 | 数量 | 占比 |
| --- | --- | ---: | ---: |
| M - Materialization | 正确中间结果没有被正确提交成最终表格 | 71 | 52.2% |
| Q - Task intent | 误解输出对象、条件、范围、行粒度或排序要求 | 31 | 22.8% |
| G - Grounding | 值读到了，但字段、实体、单位或来源解释错 | 12 | 8.8% |
| E - Extraction | 访问了正确材料但没有准确抽取原始值 | 9 | 6.6% |
| C - Computation | 证据和语义正确，但关系或数值运算错 | 5 | 3.7% |
| T - Termination | 无效迭代、预算耗尽或未提交 | 5 | 3.7% |
| D - Discovery | 选错证据来源或没有找到证据 | 3 | 2.2% |

最值得注意的是，60 个失败属于 M1：内部已有正确结果，但最终提交时多列或少列。这说明很多 Agent benchmark 如果只看“有没有找到信息”会高估 Agent 能力；面向真实业务交付，必须评测 final answer materialization。

建议截图：PDF 第 8 页 Figure 7；细节可参考 PDF 第 24 页 Table 13。

## 局限性

第一，DataSpace 的任务虽然呈现为异构 workspace，但源头主要来自 EHRSQL 和 BULL 两个 Text-to-SQL 数据集，再经过翻译、采样和渲染构造。因此，它并不是完全自然产生的企业工作区，可能仍保留 Text-to-SQL 任务的结构偏好。

第二，文档和视频是从结构化数据合成渲染出来的。论文通过 cell-level validation、视频 atom coverage、人工审核等方式控制质量，但这些材料和真实业务文档、会议视频、仪表盘录屏仍可能有分布差异。

第三，评测目标集中在完整表格输出，这非常适合 verifiable analytics，但不覆盖所有 Agent 能力。例如探索性分析、假设生成、开放式业务解释、交互式澄清、多轮协作和长期记忆等能力没有被充分评估。

第四，公开可复现性有一定限制。论文说明 410 个任务输入公开，但只有 60 个代表性任务公开 reference answers 和 evaluation configurations，其余 350 个 reference answers 用于官方完整评测。这能减少 benchmark 泄露和过拟合，但也限制了研究者完整复现实验。

第五，失败分析集中在 Grok 4.5 的失败样本，虽然很有启发，但不一定能完全代表所有 backbone 和 harness 的失败机制。不同模型可能在 discovery、extraction、grounding、computation、materialization 上有不同错误分布。

## 对 Agent 评测研究的启发

DataSpace 对 Agent 评测最有借鉴价值的地方，是把评测拆成“任务构造可信度”和“结果验证确定性”两条线。任务构造依赖 LLM，但每一步尽量通过 SQL execution、round-trip parsing、cell coverage、专家盲审来约束；结果评测则完全落到 deterministic table equivalence。这种设计比纯人工 benchmark 更可扩展，比纯 LLM judge 更可复现。

如果后续做 Agent 评测研究，可以借鉴它的几个设计点：任务应该有 task-local workspace，而不是预先指定证据；评测应该区分 available artifacts 和 required evidence；应该记录最小充分证据路径；输出契约要明确；除了 accuracy，还应报告 token、成本、动作数、延迟；失败分析不能只看最终错误类型，还要追踪最早的持久性偏离发生在哪个阶段。

这篇论文也提示了下一步评测方向：未来 benchmark 可以进一步引入更自然的企业工作区、更强的交互式澄清、更复杂的权限和数据版本冲突，以及从分析过程到最终交付物的多层级评测。

## 论文图表截图清单

| 用途 | 图表 | 位置 | 建议放置章节 |
| --- | --- | --- | --- |
| 说明任务形态 | Figure 1 | PDF 第 1 页 | 核心观点 / 背景介绍 |
| 说明 benchmark 构造流程 | Figure 2 | PDF 第 4 页 | 技术和创新点 |
| 展示数据规模 | Table 2 | PDF 第 6 页 | 技术和创新点 |
| 展示证据需求 | Figure 3 | PDF 第 6 页 | 背景介绍 / 技术和创新点 |
| 展示任务操作分布 | Figure 4 | PDF 第 6 页 | 技术和创新点 |
| 展示模型与 harness 总体结果 | Table 3 | PDF 第 7 页 | 效果总结 |
| 展示效率权衡 | Figure 5 | PDF 第 7 页 | 效果总结 |
| 展示任务特征影响 | Figure 6 | PDF 第 8 页 | 效果总结 |
| 展示失败原因 | Figure 7 | PDF 第 8 页 | 效果总结 / 局限性 |
| 展示评测配置 | Figure 18 | PDF 第 21 页 | 技术和创新点 |
| 展示详细效率表 | Table 11 | PDF 第 23 页 | 效果总结 |
| 展示详细任务特征结果 | Table 12 | PDF 第 23 页 | 效果总结 |
| 展示失败原因细分 | Table 13 | PDF 第 24 页 | 效果总结 |
