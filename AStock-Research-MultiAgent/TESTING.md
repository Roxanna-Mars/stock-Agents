# 自动化测试与评估

以下命令均在 `AStock-Research-MultiAgent` 项目根目录执行，并使用上级目录中的虚拟环境。

## 1. 安装测试依赖

```powershell
uv pip install --python '..\.venv\Scripts\python.exe' -r requirements-dev.txt
```

## 2. 日常离线测试

```powershell
& '..\.venv\Scripts\python.exe' -m pytest
```

默认命令不访问网络，也不调用 DeepSeek。`live_data` 和 `live_llm` 测试会自动跳过。

查看核心模块覆盖率：

```powershell
& '..\.venv\Scripts\python.exe' -m pytest `
  -m "not live_data and not live_llm" `
  --cov=src.utils.react_config `
  --cov=src.utils.tool_result_utils `
  --cov=src.tools.mcp_client `
  --cov=src.agents.summary_agent `
  --cov=evaluation.score_results `
  --cov-report=term-missing
```

## 3. Baostock MCP 集成测试

该测试会联网，但不会调用 DeepSeek：

```powershell
$env:RUN_LIVE_DATA = '1'
& '..\.venv\Scripts\python.exe' -m pytest -m live_data -v
Remove-Item Env:RUN_LIVE_DATA
```

它会并发发起三次贵州茅台基础信息查询，并检查：工具加载成功、结果有效、没有 `10001001` 登录冲突。

## 4. DeepSeek 完整流程测试

该测试会真实调用 API 并产生费用，必须显式开启：

```powershell
$env:RUN_LIVE_LLM = '1'
& '..\.venv\Scripts\python.exe' -m pytest -m live_llm -v
Remove-Item Env:RUN_LIVE_LLM
```

完整流程检查六个 Agent 状态、报告长度、必需章节和唯一的“分析基准时间”页脚。

## 5. 批量评估

先从一个案例开始：

```powershell
$env:RUN_LIVE_LLM = '1'
& '..\.venv\Scripts\python.exe' -m evaluation.run_evaluation --case-id maotai
Remove-Item Env:RUN_LIVE_LLM
```

确认成本和运行时间可以接受后，再执行全部五个案例：

```powershell
$env:RUN_LIVE_LLM = '1'
& '..\.venv\Scripts\python.exe' -m evaluation.run_evaluation
Remove-Item Env:RUN_LIVE_LLM
```

结果保存在 `evaluation/results/evaluation_*.json`。评分最新结果：

```powershell
& '..\.venv\Scripts\python.exe' -m evaluation.score_results --strict
```

`--strict` 会在指标未达标时返回非零退出码，适合接入 CI。默认门槛为：总体通过率至少 95%、工作流成功率至少 95%、有效报告率 100%、工具成功率至少 90%，且递归错误和 Baostock 登录冲突均为零。

## 6. Agent Benchmark v1

免费检查 24 条 Benchmark 的格式与分类：

```powershell
& '..\.venv\Scripts\python.exe' -m evaluation.run_benchmark --dry-run
```

付费运行单个案例：

```powershell
$env:RUN_LIVE_LLM = '1'
& '..\.venv\Scripts\python.exe' -m evaluation.run_benchmark --case-id single_maotai
Remove-Item Env:RUN_LIVE_LLM
```

Benchmark 会输出任务成功率、工具选择准确率、证据支撑率、重复调用率、Token 及 P50/P95 耗时，并自动归因常见失败模式。完整说明见 `evaluation/README.md`。全部运行必须显式传入 `--all`。
