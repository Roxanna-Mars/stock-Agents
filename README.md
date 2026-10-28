# Stock Agents

An open-source, evidence-grounded AI agent platform for financial research and investment analysis. The repository combines a LangGraph multi-agent application with MCP financial-data tools, deterministic Python valuation operators, provenance records, and rule-based audit checks.

> This project is for research and engineering demonstrations. It does not provide investment advice.

## What is implemented

- Existing A-share workflow with fundamental, technical, valuation, news, comparison and summary agents.
- Deterministic query routing and three evaluation architectures: Single Agent, Fixed Workflow and ReAct Multi-Agent.
- A 100-case benchmark plus unit, integration and paid live-workflow tests.
- Strict domain contracts for requests, plans, data, calculations, claims, audit findings and reports.
- Provider-neutral data registry with ordered fallback and point-in-time checks.
- Deterministic DCF, comparable-company multiples and seeded Monte Carlo DCF operators.
- Append-only provenance ledger and JSONL persistence.
- Audit rules for missing references, look-ahead data and numeric claim consistency.
- Versioned YAML playbooks for equity research, valuation, earnings review and stock comparison.
- An opt-in research graph with Lead, Data, Analysis, Modeling, Bull, Bear, Judge, Synthesis, Report and Audit roles.

The existing CLI still uses the proven A-share workflow. The new platform graph is intentionally opt-in while live providers and existing agents are migrated incrementally.

## Architecture

```text
ResearchRequest -> Lead/Plan -> Data Providers -> DataArtifact
                                      |
                                      v
                              Deterministic Compute
                             DCF / Multiples / Monte Carlo
                                      |
                                      v
Analysis -> Bull + Bear -> Judge -> Synthesis -> Report -> Audit
                \___________________________________________/
                         bounded revision on audit failure

Every layer -> Provenance Ledger -> reproducible evidence and references
```

See [architecture details](AStock-Research-MultiAgent/docs/ARCHITECTURE.md).

## Repository layout

```text
AStock-Research-MultiAgent/
  src/agents/          Existing analysis agents
  src/orchestration/   New role policies and research graph
  src/data/            Provider-neutral data contracts and fallback
  src/compute/         Deterministic financial operators
  src/audit/           Narrative/numeric consistency checks
  src/provenance/      Append-only research ledger
  src/playbooks/       YAML playbook loader and schema
  playbooks/           Versioned research procedures
  evaluation/          100-case benchmark and ablation tooling
MCP/                   A-share MCP server and financial-data tools
```

## Install

PowerShell from the repository root:

```powershell
python -m venv .venv
& '.\.venv\Scripts\Activate.ps1'
python -m pip install -r requirements.txt
python -m pip install -r AStock-Research-MultiAgent\requirements-dev.txt
Copy-Item AStock-Research-MultiAgent\.env.example AStock-Research-MultiAgent\.env
```

Fill in the OpenAI-compatible API settings in `.env`. Never commit API keys.

## Run

```powershell
Set-Location AStock-Research-MultiAgent
& '..\.venv\Scripts\python.exe' src\main.py --command "帮我分析贵州茅台(600519)是否值得投资"
```

Run the offline, deterministic audit example without an API key or network:

```powershell
& '..\.venv\Scripts\python.exe' -m examples.auditable_dcf
```

### Web interface

Install and start the local React + FastAPI platform:

```powershell
uv pip install --python '.\.venv\Scripts\python.exe' -r '.\AStock-Research-MultiAgent\web\backend\requirements.txt'

Set-Location '.\AStock-Research-MultiAgent'
& '..\.venv\Scripts\python.exe' -m uvicorn web.backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

In another terminal:

```powershell
Set-Location '.\AStock-Research-MultiAgent\web\frontend'
npm install
npm run dev
```

Open `http://localhost:5173`. See the [Web platform guide](AStock-Research-MultiAgent/web/README.md) for API and SSE details.

The Web API can route unambiguous factual questions (for example, a stock's basic information, industry, latest price or explicit-year dividend) directly to one allowlisted MCP tool without starting research or summary agents.

## Test

```powershell
& '..\.venv\Scripts\python.exe' -m pytest
```

Live tests remain disabled by default because they use external data or paid model APIs:

```powershell
$env:RUN_LIVE_DATA = '1'
& '..\.venv\Scripts\python.exe' -m pytest -m live_data -v

$env:RUN_LIVE_LLM = '1'
& '..\.venv\Scripts\python.exe' -m pytest -m live_llm -v
```

## Design references

The staged architecture is informed by [FinRobot](https://github.com/AI4Finance-Foundation/FinRobot) and [TradingAgents](https://github.com/TauricResearch/TradingAgents). No source code from either project is copied into this repository.
