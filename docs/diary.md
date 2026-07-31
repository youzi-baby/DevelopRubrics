# 今日工作总结

今天主要围绕 AdaRubric 的 rubric validation 和本地模型实验配置继续推进。首先梳理了本地 embedding 模型的接入方式，明确了即使本地服务不需要真实 API key，也最好在环境变量中写入一个非空占位值，例如 `EMPTY`，因为 OpenAI 兼容客户端通常要求 `api_key` 字段存在。随后整理了将 embedding 的 base url、model name 和 api key 永久写入用户环境变量的 PowerShell 命令，方便后续运行 validation 时不需要每次手动设置。

在方法理解上，重点检查了当前实现里的 rubric overlap validation。发现现在计算 cosine distance 时只使用了 dimension name，没有把 description 纳入 embedding 输入。因此目前的重叠检查只能判断维度名称是否相似，不能充分判断维度语义是否重叠。进一步明确了如果要增强这个检查，可以在 `adarubric/generator/validation.py` 的 `_validate_dimension_overlap()` 中，把 embedding 文本从单纯的 `dim.name` 改成 `dim.name + dim.description`，这样能更接近对维度含义的检查。

今天也重新理解了多轮 evaluation 的目的。固定 rubric 后重复跑多轮评估，并不是为了生成更高的分数，而是为了观察同一个 rubric、同一批 trajectory 在 LLM evaluator 下的评分稳定性，包括 global score 的波动、good/weak trajectory 的排序是否稳定，以及 pass/fail 结果是否会因为模型随机性而改变。

最后，对论文中的 rubric validation 方法形成了一个比较明确的判断：原论文的三项检查更像是最低限度的结构合法性检查，而不是真正的 rubric 质量筛选。dimension name 很容易在 embedding 空间中显得正交，权重和为 1、评分等级齐全也都属于比较容易满足的格式要求。因此如果后续要筛选“更好的 rubric”，还需要加入更强的质量评估，例如 task relevance、criteria specificity、observable from trajectory、维度语义冗余检查，以及用 good/weak/partial/irrelevant trajectory 做 discriminative power 测试。
