# AI Cargo Monitoring -- Progress Report & Task Distribution

## System Layers

```
L1  Data + Risk Engine        DONE     Rahul
L2  Agent Tools               DONE     Rahul
L3  Orchestration Agent       WIP      Teammate (mock-agent testing)
L4  FastAPI Backend            DONE     Rahul
L5  React Dashboard            DONE     Rahul
L6  Integration + E2E Tests   NEXT     Joint
```

## Task Ownership

### Rahul -- Risk Engine, Tools, Backend, Dashboard

| #  | Task                                 | Status   | Depends on | Notes |
|----|--------------------------------------|----------|------------|-------|
| 1  | Synthetic data audit & EDA           | DONE     | --         | 7 408 rows, 6 products, quality findings documented |
| 2  | Product profiles (WHO thresholds)    | DONE     | --         | `data/product_profiles.json` |
| 3  | Feature engineering module           | DONE     | 1          | 14 derived features, per-leg rolling/lag |
| 4  | Deterministic rule engine            | DONE     | 2, 3       | 7 product-aware rules, composite 0-1 score |
| 5  | Predictive ML model (XGBoost)        | DONE     | 3          | Optuna-tuned, SHAP explainability, 96% recall |
| 6  | Risk fusion layer                    | DONE     | 4, 5       | alpha-blend + deterministic veto |
| 7  | Compliance logger                    | DONE     | 6          | JSONL audit records per window |
| 8  | LangGraph risk-scoring pipeline      | DONE     | 3-7        | `pipeline.py` -- train or score mode |
| 9  | Agent tools (LangChain-compatible)   | DONE     | --         | 8 tools: route, cold_storage, notification, compliance, scheduling, insurance, triage, approval |
| 10 | Pydantic schemas (shared models)     | DONE     | --         | Matches `system_prompt.md` input/output contract |
| 11 | FastAPI backend                      | DONE     | 8, 9, 10   | REST + WebSocket, serves risk data + tool execution |
| 12 | React dashboard                      | DONE     | 11         | Risk overview, shipment list, detail, audit log, approvals |
| 13 | Integration test (E2E)               | DONE     | 9-12       | Backend + frontend running, all endpoints verified |

### Teammate -- Orchestration Agent

| #  | Task                                    | Status   | Depends on         | Notes |
|----|-----------------------------------------|----------|--------------------|-------|
| A  | System prompt design                    | DONE     | --                 | `system_prompt.md` |
| B  | LangGraph orchestration graph           | WIP      | A                  | Plan → Reflect → Revise → Execute loop |
| C  | Mock agent integration tests            | WIP      | A, B               | Testing with simulated risk inputs |
| D  | Connect to real tools (Rahul's #9)      | BLOCKED  | B, 9               | Swap mocks for LangChain tool wrappers |
| E  | Connect to real backend (Rahul's #11)   | BLOCKED  | B, 11              | Wire orchestrator → FastAPI endpoints |
| F  | Human-in-the-loop approval flow         | BLOCKED  | B, D, 12           | Dashboard approval UI + WebSocket events |

## Dependency Graph

```
Data(1) ──► Features(3) ──► Deterministic(4) ──► Fusion(6) ──► Pipeline(8) ──► Backend(11) ──► Dashboard(12)
  │                    └──► ML Model(5) ──────┘       │                           ▲
  └──► Profiles(2) ──────────────────────────────────┘                           │
                                                                                  │
Tools(9) + Schemas(10) ─────────────────────────────────────────────────────────┘
                                │
                Orchestrator(B) ◄── System Prompt(A)
                        │
                  Mock Tests(C) ──► Real Tools(D) ──► Real Backend(E) ──► Approval Flow(F)
```

## Integration Handoff Checklist

When the orchestrator is ready to connect to real infrastructure:

- [ ] Import tools from `AI_cargo/tools/` as LangChain `StructuredTool` objects
- [ ] Call `POST /api/risk/score-window` to get risk engine output for a window
- [ ] Feed that output to the orchestration agent as the structured input from `system_prompt.md`
- [ ] Orchestrator calls tools via LangGraph `ToolNode` or direct `.invoke()`
- [ ] Tool results are written back via `POST /api/tools/{tool_name}/execute`
- [ ] Dashboard polls `/api/events` (WebSocket) for live updates
- [ ] HIGH/CRITICAL actions that need approval go through `POST /api/approval/request`
- [ ] Dashboard shows approval queue; operator approves via `POST /api/approval/{id}/decide`

## Data Quality Actions (pending)

| Issue | Priority | Owner |
|-------|----------|-------|
| shock_count 99.7% zeros  | Medium | Rahul (data gen update) |
| door_open_count 99.8% zeros | Medium | Rahul (data gen update) |
| P03 zero spoilage events | Low | Rahul |
| Add product temp ranges to CSV | Low | Rahul |
