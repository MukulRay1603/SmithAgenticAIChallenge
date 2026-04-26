# AI Cargo Monitor

[![Live Demo](https://img.shields.io/badge/Live%20Demo-ai--cargo--monitor-8B5CF6?style=flat-square&logo=vercel)](https://ai-cargo-monitor-prod.vercel.app)
[![Winner](https://img.shields.io/badge/UMD%20Smith%20Agentic%20AI%20Challenge-$4%2C000%20Winner-gold?style=flat-square)](https://smith.umd.edu)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-Orchestration-1C3A5E?style=flat-square)](https://langchain.com/langgraph)
[![React](https://img.shields.io/badge/React-Vite%20Dashboard-61DAFB?style=flat-square&logo=react)](https://react.dev)

**AI Decision Intelligence for Pharmaceutical Cold Chain**

> Monitoring tells you what happened. This system decides what to do.

Pharmaceutical cold-chain failures cost **$35 billion annually**. The problem is not detection — sensors work. The problem is the gap between detection and intelligent action. A temperature excursion triggers an alert; a human reads it 47 minutes later, finds a QA manager, manually searches 417 regulatory documents, gets director approval, and finally contacts the hospital. By then the product is gone.

AI Cargo Monitor closes that gap. It ingests real-time shipment telemetry, scores spoilage risk using a hybrid ML + deterministic engine, and autonomously orchestrates a cascade of operational decisions — rerouting, cold storage, appointment rescheduling, insurance claim drafting — in 12–15 seconds, with a human approval gate before any irreversible action fires.

---

## Live System

**→ [ai-cargo-monitor-prod.vercel.app](https://ai-cargo-monitor-prod.vercel.app)**

Backend: Railway · Frontend: Vercel · Data: Supabase · LLM: Groq (primary)

---

## Architecture

The system is five layers, each with a single responsibility:
```
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 1 · Data Pipeline                                            │
│  IoT telemetry → Supabase (window_features) + local CSV fallback    │
│  Real APIs: OpenSky flight delays · Open-Meteo ambient temperature  │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 2 · Hybrid Risk Scoring                                      │
│  8 deterministic rules + XGBoost (Optuna-tuned) + SHAP explainer    │
│  Fused score → SAFE / WARN / HIGH / CRITICAL tier                   │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 3 · Context Engineering                                      │
│  delay_ratio · delay_class · hours_to_breach · facility enrichment  │
│  Builds the risk_input contract for the orchestrator                │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 4 · Agentic Orchestration                                    │
│  LangGraph state machine: interpret → plan → execute →              │
│  observe → reflect → revise → human gate → final output             │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 5 · React Dashboard                                          │
│  8 pages · WebSocket live updates · Human Review Queue              │
│  Overview · Monitoring · Shipments · Agent Activity · Audit Log     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Risk Intelligence Engine

The core of the system is a hybrid scoring pipeline that fuses two independent signals:

**Layer A — Deterministic rule engine (8 rules)**

| Rule | Trigger | Sub-score |
|------|---------|-----------|
| `temp_critical_breach` | Temperature outside critical bounds | 0.60 |
| `temp_warning_breach` | Temperature outside safe bounds | 0.30 |
| `temp_trend_warning` | Slope > 1°C/hr approaching boundary | up to 0.20 |
| `excursion_duration` | Cumulative breach exceeds product limit | up to 0.30 |
| `delay_temp_stress` | Delay > 120 min + temp near boundary | up to 0.25 |
| `freeze_risk` | Below 0°C for freeze-sensitive products (WHO PQS E006) | 0.50 |
| `battery_critical` | Battery below 15% | 0.15 |
| `shock_event` | Any shock or door-open event | up to 0.15 |

Rules fire instantly, are fully auditable, and cannot be overridden by the ML layer when `det_score ≥ 0.8` (deterministic veto).

**Layer B — XGBoost predictive model**

Trained on 7,411 scored telemetry windows across 6 product profiles and 6 facilities. Predicts spoilage risk 6 hours ahead. Hyperparameters tuned via 30-trial Optuna search (maximises PR-AUC). SHAP values explain every prediction — required for FDA 21 CFR Part 11 auditability.

**Fusion**
```
fused_score = 0.4 × det_score + 0.6 × ml_score
— but if det_score ≥ 0.8:
fused_score = max(det_score, blended)
```

The deterministic layer can only raise the final score, never lower it below what the rules found. A missed spoilage costs millions; a false alert costs a phone call.

---

## Agentic Orchestration Loop

When `fused_score` crosses a tier threshold, the LangGraph orchestrator activates:
```
interpret risk
↓
plan (LLM or deterministic template)
↓
execute cascade (agents run sequentially, each inheriting prior results)
↓
observe (tool success/failure analysis)
↓
reflect (GAP / QUALITY notes on execution)
↓
revise (corrective steps if gaps found or tools deferred)
↓
◉ human review gate ← ALL MEDIUM+ pauses here
↓
notification fires (only after approval)
```

Every agent result becomes the next agent's context automatically — no independent lookups. The compliance `log_id` flows into the insurance claim. The cold storage facility name flows into the scheduling agent. The orchestrator accumulates a `cascade_context` dict that grows richer at every step.

---

## Agent Roster

| Agent | Role | Type |
|-------|------|------|
| **Triage** | Ranks at-risk shipments by urgency before orchestration begins | Deterministic |
| **Compliance** | RAG search across 417 regulatory chunks (WHO / EU GDP / FDA 21 CFR) | LLM + RAG |
| **Cold Storage** | Scores backup facilities by temp compatibility, proximity, capacity | Deterministic |
| **Route** | Selects alternative cold-chain route via rule table + LLM candidate selection | Hybrid |
| **Scheduling** | Reschedules downstream appointments; ranks by patient urgency and disruption cost | Deterministic |
| **Insurance** | Computes 4-component itemised loss; assembles claim package for director sign-off | Deterministic |
| **Approval** | Human-in-the-loop gate; holds all MEDIUM+ actions pending operator decision | HITL |
| **Notification** | Multi-channel stakeholder alerts (email / Slack / dashboard) post-approval | LLM-driven |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Orchestration | LangGraph (StateGraph with typed state) |
| LLM providers | Groq (primary) → OpenAI → Anthropic → Ollama (offline fallback) |
| ML | XGBoost · Optuna · SHAP · scikit-learn |
| Backend | FastAPI · Python 3.11 · WebSocket |
| Database | Supabase (PostgreSQL + pgvector) |
| RAG | ChromaDB / Supabase pgvector · Sentence Transformers |
| Frontend | React 18 · Vite · Recharts |
| Deployment | Railway (backend) · Vercel (frontend) |
| External APIs | OpenSky Network (flight delays) · Open-Meteo (ambient temperature) |

**LLM provider fallback chain** — the system never goes dark. If Groq is unavailable or rate-limited, it switches to OpenAI, then Anthropic, then Ollama running fully offline with no internet dependency. One environment variable controls priority order; zero redeployment required.

---

## Key Numbers

| Metric | Value |
|--------|-------|
| Telemetry windows scored | 7,411 |
| Product profiles | 6 |
| Facilities modelled | 6 |
| Regulatory chunks (RAG corpus) | 417 |
| Deterministic risk rules | 8 |
| Specialized agents | 8 |
| API endpoints | 25+ |
| LLM providers (fallback chain) | 4 |
| Agentic response time | ~12–15 seconds |
| Deterministic fallback response | < 1 second |
| Dashboard pages | 8 |
| E2E tests | 30+ |

---

## My Contributions

*This fork is maintained by [Mukul Ray](https://github.com/MukulRay1603). Component-level attribution is in [CONTRIBUTORS.md](./CONTRIBUTORS.md). Below is what I designed and built.*

**Route Agent** (`tools/route_agent.py`)

Hybrid rule-based + LLM-assisted route selection for cold-chain shipments under risk. The agent classifies each product into a temperature class (frozen / refrigerated / CRT), looks up candidate routes from a curated route table, then optionally asks the active LLM to select the best candidate given real Supabase route context — actual origin, destination, carrier, weather condition, and delay probability. Falls back gracefully to deterministic rule selection on any LLM failure. `requires_approval` is always `True`; route changes are irreversible.

**Triage Agent** (`tools/triage_agent.py`) + triage API endpoints

Ranks multiple at-risk shipments by urgency before any orchestration decisions are made. Two-key sort: tier priority first (CRITICAL=0, HIGH=1, MEDIUM=2, LOW=3), then `fused_risk_score` descending within tier. Enriches each shipment from `scored_windows.csv` with `hours_at_risk`, `peak_temp_c`, and `primary_breach_rule`. The `recommended_orchestration_order` output (CRITICAL + HIGH only) is what the LangGraph planner uses when running batch orchestration. Also built the backend API endpoints: `GET /api/triage/critical-shipments` and `POST /api/triage/rank`.

**Insurance Agent cascade design** (`tools/insurance_agent.py`)

Designed the cascade position and integration contract: called after compliance and cold storage, receives the compliance `log_id` as `supporting_evidence` via `_enrich_tool_input`, creating a direct audit chain from regulatory decision to financial claim. The assembled package never fires automatically — it routes to the human approval gate by design.

**LLM Provider Fallback Chain** (`orchestrator/llm_provider.py`)

Designed the 4-provider hot-swap architecture: Groq → OpenAI → Anthropic → Ollama. Priority order is configurable via `CARGO_LLM_PRIORITY` environment variable with zero redeployment. Ollama enables full offline operation for clients requiring data sovereignty. The system degrades gracefully to deterministic-only mode if no provider is available, rather than failing.

**Scalability & Containerisation architecture**

Designed the deployment model: single Docker image, device-agnostic (sits above any existing Sensitech / Tive / Controlant tracker hardware without rip-and-replace), offline-resilient via local CSV/JSON fallback. Cost model: ~$200K one-time setup, ~$10K/month recurring. One prevented biologic loss ($215K average) covers 12 months of operation.

**Bug fix: `_should_revise()` in orchestrator/graph.py**

The original implementation unconditionally routed every orchestration run through the revise node, wasting one full LLM call per incident regardless of whether reflection found any issues. Fixed to check for GAP notes in reflection output and deferred tools before routing, making the logic explicit and eliminating unnecessary LLM spend on clean executions.

---

## Team Synapse

| Member | Primary Components |
|--------|--------------------|
| Rahul Sharma | LangGraph orchestrator · ML pipeline · XGBoost · feature engineering |
| Karthik | Data pipeline · Supabase schema · product and facility data |
| Mukul Ray *(this fork)* | Route agent · Triage agent · Insurance cascade · LLM fallback chain · Scalability |
| Yash | Compliance agent · RAG pipeline · Notification agent · Slack/email integration |
| Nikhil Sumesh | Scheduling agent · Cold storage agent · Deployment · Railway/Vercel |

---

## Competition

**UMD Smith School of Business · Agentic AI Challenge · April 2026**
**1st Place — $4,000**

Challenge: Design an agentic AI system capable of triggering cascading operational actions when pharmaceutical shipment risks are detected — balancing automation with regulatory constraints, explainability, and human-in-the-loop oversight.

Original repository: [nsumesh/SmithAgenticAIChallenge](https://github.com/nsumesh/SmithAgenticAIChallenge)

---

*Monitoring tells you what happened. We built the system that decides what to do.*
