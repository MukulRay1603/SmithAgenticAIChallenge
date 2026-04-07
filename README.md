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
# 1. Install Python dependencies
cd AI_cargo
pip install -r requirements.txt

# 2. Train the risk model (runs LangGraph scoring pipeline)
python3 pipeline.py train

# 3. Start the FastAPI backend
python3 -m uvicorn backend.app:app --port 8000

# 4. Install and start the React dashboard
cd dashboard
npm install
npm run dev

# Dashboard is live at http://localhost:5173
# API docs at http://localhost:8000/docs
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
├── orchestrator/               Orchestration agent (LangGraph)
│   ├── state.py                OrchestratorState TypedDict
│   ├── nodes.py                Node functions: interpret, plan, reflect...
│   └── graph.py                StateGraph construction + Mermaid export
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

## Orchestration Agent

The orchestration agent is a LangGraph `StateGraph` that implements a
plan-reflect-execute loop:

```
interpret_risk → plan → reflect → [revise if gaps] → execute → fallback → output
```

- **Interpret**: classifies severity, identifies primary issue from rule flags
- **Plan**: generates a multi-step tool-calling plan based on tier templates
- **Reflect**: self-critiques against a compliance checklist (5 checks)
- **Revise**: patches the plan to fix gaps found during reflection
- **Execute**: calls tools sequentially via LangChain StructuredTool.invoke()
- **Fallback**: prepares a minimal backup plan if primary execution fails
- **Output**: compiles the final structured decision (matches system_prompt.md)

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

## Tech Stack

- **Risk Engine**: Python, pandas, scikit-learn, XGBoost, SHAP, Optuna
- **Orchestration**: LangGraph, LangChain Core
- **Backend**: FastAPI, Pydantic, uvicorn
- **Frontend**: React 19, Vite, Tailwind CSS v4, Recharts, Mermaid
- **Compliance**: JSONL audit logs, SHAP explainability, human-in-the-loop
