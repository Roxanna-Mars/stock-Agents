# Agent Evaluation Experiments

## 三种架构

- `single_agent`：单个 ReAct 研究 Agent 完成规划、取数和分析。
- `fixed_workflow`：固定运行基本面、技术面、估值和新闻四个分支。
- `react_multi_agent`：按任务路由到最小必要 Agent 集合，并支持独立多股比较 Agent。

三种架构都复用同一个 Summary Agent 作为输出格式化与证据引用层；“Single-Agent”指只有一个研究 Agent，避免因为报告模板不同而污染架构对照结果。

## 免费检查实验计划

```powershell
& '..\.venv\Scripts\python.exe' -m evaluation.run_ablation `
  --category focused_analysis --repeats 2 --dry-run
```

该命令只校验案例、架构和计划运行次数，不调用模型或数据 API。

## 小规模真实消融

建议先选择少量代表性案例控制费用：

```powershell
$env:RUN_LIVE_LLM = '1'
& '..\.venv\Scripts\python.exe' -m evaluation.run_ablation `
  --case-id focus_maotai_technical `
  --case-id compare_liquor `
  --case-id calc_maotai_margin `
  --case-id robust_conflicting_evidence `
  --repeats 2
Remove-Item Env:RUN_LIVE_LLM
```

每种架构会生成独立 JSON，并自动输出相对于 Single-Agent、Fixed Workflow 以及“任务成功率最高基线”的任务成功率、工具选择、证据引用、时延和 Token 差异。重复运行至少两次时，还会基于相同工具及参数的返回摘要计算 `data_consistency_rate`。

运行全部 100 条案例、3 种架构、每条重复 2 次将产生 600 次完整工作流，费用和耗时较高，必须额外传入 `--all`。

## 优化前后版本对比

保存一次基线结果和一次优化后结果后，运行：

```powershell
& '..\.venv\Scripts\python.exe' -m evaluation.compare_results `
  evaluation/results/baseline.json `
  evaluation/results/candidate.json `
  --output evaluation/results/version_comparison.md
```

结果包含成功率和工具选择准确率的百分点变化、平均/P95 时延变化、Token 变化、证据指标变化及各类失败次数变化，可用于填写简历中的实测数据。
