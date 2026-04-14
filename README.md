# AI Cargo Monitor -- Pharmaceutical Cold-Chain Risk Intelligence

An end-to-end agentic AI system that monitors temperature-sensitive pharmaceutical
shipments, predicts spoilage risk, orchestrates mitigation actions, and maintains
FDA/GDP compliance -- all through a LangGraph-powered pipeline with a React dashboard.

## Architecture

```
 IoT Sensors ─────► Window Aggregation ─────► Feature Engineering
                                                    │
                                    ┌───────────────┴───────────────┐
                                    ▼                               ▼
                          Deterministic Rules              XGBoost Predictor
                          (7 product-aware)                (Optuna + SHAP)
                                    │                               │
                                    └───────────┬───────────────────┘
                                                ▼
                                          Risk Fusion
                                     (alpha-blend + veto)
                                                │
                                                ▼
                                    Orchestration Agent (LangGraph)
                              interpret → plan → reflect → revise → execute
                                                │
                        ┌───────┬───────┬───────┼───────┬───────┬───────┐
                        ▼       ▼       ▼       ▼       ▼       ▼       ▼
                      Route   Cold    Notify  Comply  Insure  Sched   Approve
                      Agent  Storage  Agent   Agent   Agent   Agent   Workflow
                                                │
                                                ▼
                                         Ops Dashboard
                                     (React + Recharts)
```

## Quick Start

```bash
# 1. Create virtual environment
cd AI_cargo
python3 -m venv .venv && source .venv/bin/activate

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Train the risk model (runs LangGraph scoring pipeline)
python3 pipeline.py train

# 4. Start Ollama for agentic mode (optional -- falls back to deterministic)
ollama pull qwen2.5:7b

# 5. Start the FastAPI backend
python3 -m uvicorn backend.app:app --port 8000

# 6. Install and start the React dashboard
cd dashboard
npm install
npm run dev

# Dashboard is live at http://localhost:5173
# API docs at http://localhost:8000/docs
```

### LLM Configuration

The orchestrator supports multiple LLM providers with automatic fallback:

```bash
# Priority order (default: ollama first)
export CARGO_LLM_PRIORITY="ollama,openai,anthropic"

# Ollama (local, free)
export CARGO_OLLAMA_MODEL="qwen2.5:7b"

# OpenAI (cloud)
export OPENAI_API_KEY="sk-..."
export CARGO_OPENAI_MODEL="gpt-4o-mini"

# Anthropic (cloud)
export ANTHROPIC_API_KEY="sk-ant-..."
export CARGO_ANTHROPIC_MODEL="claude-3-5-haiku-latest"

# Disable LLM entirely (deterministic mode)
export CARGO_LLM_ENABLED=0
```

Or configure at runtime via API:
```bash
curl -X POST http://localhost:8000/api/llm/configure \
  -H "Content-Type: application/json" \
  -d '{"openai_api_key": "sk-...", "priority": "openai,ollama"}'
```

## Project Structure

```
AI_cargo/
│
├── pipeline.py                 LangGraph risk-scoring pipeline (train/score)
├── system_prompt.md            Orchestrator agent system prompt
├── requirements.txt            Python dependencies
├── ARCHITECTURE.md             System architecture document
├── PROGRESS_REPORT.md          Task tracking & team distribution
│
├── data/
│   ├── single_table.csv        7,408 telemetry windows (synthetic)
│   └── product_profiles.json   WHO-aligned temperature thresholds
│
├── src/                        Risk scoring engine
│   ├── data_loader.py          Load, validate, shipment-stratified split
│   ├── feature_engineering.py  14 derived features (rolling, lag, deviation)
│   ├── deterministic_engine.py 7 product-aware rules → composite score
│   ├── predictive_model.py     XGBoost + Optuna + SHAP explainability
│   ├── risk_fusion.py          Weighted blend + deterministic veto
│   └── compliance_logger.py    JSONL audit records per window
│
├── orchestrator/               Agentic orchestration (LangGraph)
│   ├── state.py                OrchestratorState TypedDict
│   ├── nodes.py                Deterministic node functions + cascade enrichment
│   ├── llm_nodes.py            Agentic LLM-powered plan + reflect nodes
│   ├── llm_provider.py         Multi-provider LLM abstraction (Ollama/OpenAI/Anthropic)
│   └── graph.py                StateGraph construction + mode switching
│
├── tools/                      LangChain StructuredTools (8 agents)
│   ├── route_agent.py          Alternative route recommendations
│   ├── cold_storage_agent.py   Backup cold-storage facility lookup
│   ├── notification_agent.py   Stakeholder alerts (ops, clinic, hospital)
│   ├── compliance_agent.py     Immutable audit log (GDP/FDA/WHO)
│   ├── scheduling_agent.py     Facility reschedule recommendations
│   ├── insurance_agent.py      Claim documentation preparation
│   ├── triage_agent.py         Multi-shipment urgency ranking
│   └── approval_workflow.py    Human-in-the-loop approval queue
│
├── backend/                    FastAPI REST + WebSocket API
│   ├── app.py                  Endpoints: risk, shipments, tools, orchestrator
│   └── models.py               Pydantic schemas (risk engine ↔ orchestrator)
│
├── dashboard/                  React + Vite + Tailwind + Recharts
│   └── src/components/
│       ├── Overview.jsx        KPI cards, tier pie chart, risky shipments
│       ├── Monitoring.jsx      Live risk feed, alert banners
│       ├── ShipmentList.jsx    Filterable shipment table
│       ├── ShipmentDetail.jsx  Temp + risk timelines, window table
│       ├── AgentActivity.jsx   Orchestrator decisions, tool results
│       ├── GraphView.jsx       Mermaid-rendered system + agent graphs
│       ├── AuditLog.jsx        Compliance records with SHAP features
│       └── Approvals.jsx       Human approval queue (approve/reject)
│
├── artifacts/                  Generated outputs
│   ├── xgb_spoilage.joblib    Trained XGBoost model
│   └── scored_windows.csv     Full scored dataset
│
├── audit_logs/                 Compliance audit trail (JSONL)
└── notebooks/
    └── 01_eda_data_quality.ipynb   EDA & data quality report
```

## Hybrid Risk Scoring

The system combines two independent scoring layers:

**Deterministic rules** (instant, auditable):
- Temperature breach (product-specific ranges from WHO guidelines)
- Temperature trend (slope heading toward boundary)
- Excursion duration (cumulative minutes outside range)
- Battery critical (sensor monitoring loss risk)
- High humidity (condensation / packaging degradation)
- Delay + temperature stress (compound risk)
- Shock / door-open events (handling incidents)

**XGBoost predictor** (learned, probabilistic):
- 14 engineered features (rolling stats, lag transforms, progress indicators)
- Optuna-tuned hyperparameters (30 trials, PR-AUC objective)
- SHAP values for every prediction (regulatory explainability)
- Shipment-stratified train/val/test split (no temporal leakage)

**Fusion**: `final = 0.4 * deterministic + 0.6 * ML`, with deterministic veto
for critical breaches (score > 0.8 cannot be reduced by ML).

| Tier     | Score Range | Action                           |
|----------|-------------|----------------------------------|
| LOW      | 0.0 -- 0.3  | Standard monitoring              |
| MEDIUM   | 0.3 -- 0.6  | Increased frequency, pre-alert   |
| HIGH     | 0.6 -- 0.8  | Active intervention, notify ops  |
| CRITICAL | 0.8 -- 1.0  | Immediate action, human approval |

## Agentic Orchestration

The orchestration agent is a LangGraph `StateGraph` that implements a
plan-reflect-revise-execute loop. In **agentic mode**, the LLM decides which
tools to call AND constructs the tool input payloads -- it is not a template
executor.

```
interpret_risk → plan (LLM) → reflect (LLM) → [revise if gaps] → execute → fallback → output
```

- **Interpret**: classifies severity, identifies primary issue from rule flags
- **Plan (agentic)**: LLM analyzes the risk event, reasons about what actions are needed, selects tools, and constructs input payloads using the actual shipment/risk data
- **Reflect (agentic)**: LLM critiques the plan against compliance requirements, identifies missing tools or gaps
- **Revise**: patches the plan to fix any gaps the LLM found during reflection
- **Execute**: calls tools sequentially with **cascade enrichment** -- each tool's output enriches the inputs to downstream tools (e.g., cold_storage result feeds into notification and scheduling)
- **Fallback**: prepares a minimal backup plan if primary execution fails
- **Output**: compiles the final structured decision with LLM reasoning trace

### Agentic vs Deterministic

| Feature | Agentic Mode | Deterministic Mode |
|---------|-------------|-------------------|
| Plan generation | LLM reasons about situation, picks tools | Tier-based templates |
| Tool inputs | LLM constructs from risk data | `_build_tool_input()` function |
| Reflection | LLM compliance critique | Checklist-based pattern matching |
| Cascade enrichment | Applied on top of LLM inputs | Applied on top of template inputs |
| Latency | ~15-40s (depends on provider) | <1s |
| Provider | Ollama / OpenAI / Anthropic | None needed |

### Multi-Provider LLM System

The system tries providers in priority order and uses the first one that responds:

1. **Ollama** (default first) -- local, free, `qwen2.5:7b`
2. **OpenAI** -- cloud, requires `OPENAI_API_KEY`
3. **Anthropic** -- cloud, requires `ANTHROPIC_API_KEY`

Priority is configurable via `CARGO_LLM_PRIORITY` env var or the `/api/llm/configure` endpoint.
API keys can be set at runtime without server restart.

### Cascade Enrichment (Nikhil's Design)

During execution, each tool's output flows into subsequent tools:
- `cold_storage_agent` result → `notification_agent` gets facility name
- `compliance_agent` log_id → `insurance_agent` gets supporting evidence
- Delay computation → `scheduling_agent` gets revised ETA
- All tool results → `approval_workflow` gets consolidated action summaries

### Why LangGraph, not n8n or Make?

| Concern | LangGraph | n8n / Make |
|---------|-----------|------------|
| Conditional branching | Native (conditional_edges) | Limited |
| State management | TypedDict flows through graph | Stateless triggers |
| Tool calling | LangChain StructuredTool | HTTP webhooks only |
| Explainability | SHAP + audit at every node | No built-in |
| Compliance audit | Immutable logs per decision | No native support |
| Python ML integration | Direct (XGBoost, pandas) | Requires API wrapper |
| Graph visualization | Built-in Mermaid export | Visual editor only |

LangGraph gives us programmatic control over every decision point,
which is non-negotiable for FDA 21 CFR Part 11 compliance.

## Data Quality Findings

| Finding | Impact | Status |
|---------|--------|--------|
| `shock_count` 99.7% zeros | Low ML signal | Flagged for data gen update |
| `door_open_count` 99.8% zeros | Low ML signal | Flagged for data gen update |
| `minutes_outside_range > 0` implies target=1 | Leaky feature | Used in det only; lag-transformed for ML |
| P03 zero spoilage events | Under-modeled | Add CRT excursion scenarios |
| P06: 37.8% spoilage rate | Dominates positives | Handled via stratified split |
| 17% class imbalance | ML bias | scale_pos_weight=4.9 in XGBoost |

## Model Performance

| Metric | Validation | Test |
|--------|-----------|------|
| PR-AUC | 0.9987 | 0.5822 |
| ROC-AUC | 0.9997 | 0.9446 |
| F1 | 0.9742 | 0.4118 |

Tier-level performance (full dataset, 7,408 windows):
- **CRITICAL**: 927 windows, 100% precision (all true positives)
- **HIGH**: 51 windows, 98% precision
- **MEDIUM**: 304 windows, 77% precision
- **Overall recall at any non-LOW tier**: 96% (1,211 of 1,261 positives caught)

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/risk/overview` | GET | Tier distribution, KPIs, top risky shipments |
| `/api/shipments` | GET | All shipments, filterable by `risk_tier` |
| `/api/shipments/{id}/windows` | GET | All windows for a shipment |
| `/api/windows` | GET | Windows, filterable by tier/product, paginated |
| `/api/risk/score-window/{id}` | GET | Risk engine output for orchestrator |
| `/api/orchestrator/run/{id}` | POST | Run orchestration agent on a window |
| `/api/orchestrator/run-batch` | POST | Orchestrate multiple windows |
| `/api/orchestrator/history` | GET | Recent orchestrator decisions |
| `/api/tools/{name}/execute` | POST | Execute any agent tool |
| `/api/graph/mermaid` | GET | Orchestrator graph as Mermaid string |
| `/api/graph/topology` | GET | Full 5-layer system topology as JSON |
| `/api/audit-logs` | GET | Compliance audit records |
| `/api/approvals/pending` | GET | Pending human approval requests |
| `/api/approvals/{id}/decide` | POST | Approve or reject an action |
| `/api/llm/status` | GET | Active LLM provider, available providers, config |
| `/api/llm/configure` | POST | Hot-configure API keys, priority, models |
| `/api/orchestrator/mode` | GET | Current orchestrator mode (agentic/deterministic) |

## Tech Stack

- **Risk Engine**: Python, pandas, scikit-learn, XGBoost, SHAP, Optuna
- **Orchestration**: LangGraph, LangChain Core, LangChain Ollama/OpenAI/Anthropic
- **LLM**: Ollama (qwen2.5:7b default) + OpenAI + Anthropic with automatic fallback
- **Backend**: FastAPI, Pydantic, uvicorn
- **Frontend**: React 19, Vite, Tailwind CSS v4, Recharts, Mermaid
- **Compliance**: JSONL audit logs, SHAP explainability, human-in-the-loop
