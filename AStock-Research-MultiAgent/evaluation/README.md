# Agent Benchmark v1

架构消融、重复运行和版本对比命令见 [EXPERIMENTS.md](EXPERIMENTS.md)。

`benchmark_v1.jsonl` 包含 100 条任务：单股综合分析 20 条、专项分析 25 条、多股比较 20 条、财务计算 20 条、鲁棒性 15 条。

- `support_level=supported`：当前系统应当能够完成，用于回归测试。
- `support_level=target`：下一阶段目标能力，用于暴露缺口，不代表已经实现。

## 免费校验

```powershell
& '..\.venv\Scripts\python.exe' -m evaluation.run_benchmark --dry-run
```

该命令只检查 Schema、案例数量和分类，不访问网络或模型。

## 付费运行

先运行一个案例：

```powershell
$env:RUN_LIVE_LLM = '1'
& '..\.venv\Scripts\python.exe' -m evaluation.run_benchmark --case-id single_maotai
Remove-Item Env:RUN_LIVE_LLM
```

按类别运行：

```powershell
$env:RUN_LIVE_LLM = '1'
& '..\.venv\Scripts\python.exe' -m evaluation.run_benchmark --category single_stock
Remove-Item Env:RUN_LIVE_LLM
```

全部运行必须显式添加 `--all`，防止误耗 API 额度。

## 指标

- `task_success_rate`：进程、工作流、预期 Agent、报告与工具选择均通过的任务比例。
- `tool_selection_accuracy`：预期工具组命中和禁用工具规避的规则化得分。
- `tool_success_rate`：有可用返回的工具调用比例。
- `evidence_grounding_rate`：报告中证据引用 ID 的有效率；数值原文匹配率另记为 `numeric_evidence_grounding_rate`。
- `duplicate_tool_call_rate`：同一 Agent 使用相同参数重复调用同一工具的比例。
- `p50/p95_duration_seconds`：端到端耗时分位数。
- `total_tokens/average_tokens`：模型返回的 Token 元数据汇总；供应商未返回时为零。

数值证据支撑率是确定性启发式指标：它适合做版本间回归比较，但不能替代人工金融事实核验，也不能识别由原始数据计算得到、但未在工具输出中直接出现的衍生指标。

## 失败归因

评分器会标注超时、Agent 未完成、报告缺失、工具遗漏、工具误选、重复调用、工具执行错误和证据缺口。原始逐次工具响应保存在对应执行目录的 `tools/*.jsonl`。
