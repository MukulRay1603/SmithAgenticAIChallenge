# Contributors

Team Synapse — UMD Smith School of Business Agentic AI Challenge, April 2026
**Winner — $4,000**

Live demo: https://ai-cargo-monitor-prod.vercel.app  
GitHub: https://github.com/nsumesh/SmithAgenticAIChallenge

---

## Component Ownership

| Component | Owner(s) | Files |
|-----------|----------|-------|
| Data pipeline · Supabase schema · product/facility data | Karthik | `src/supabase_client.py`, `src/data_loader.py`, `data/` |
| ML pipeline · XGBoost · SHAP · feature engineering | Rahul Sharma | `src/predictive_model.py`, `src/feature_engineering.py`, `src/risk_fusion.py`, `pipeline.py` |
| LangGraph orchestrator · plan/reflect/revise loop | Rahul Sharma | `orchestrator/` |
| Compliance agent · RAG pipeline · 417 regulatory chunks | Yash | `backend/agents/compliance/`, `tools/compliance_agent.py`, `tools/helper/` |
| Notification agent · email · Slack webhook | Yash | `tools/notification_agent.py`, `tools/helper/notification/` |
| Scheduling agent · feasibility checks · priority ranking | Nikhil Sumesh | `tools/scheduling_agent.py` |
| Cold storage agent · facility scoring · temp compatibility | Nikhil Sumesh | `tools/cold_storage_agent.py` |
| Deployment · Railway · Vercel · Docker configuration | Nikhil Sumesh | `railway.toml`, `dashboard/vercel.json` |
| **Route agent · temp class taxonomy · LLM + rule hybrid** | **Mukul Ray** | **`tools/route_agent.py`** |
| **Triage agent · urgency ranking · enrichment** | **Mukul Ray / Rahul Sharma** | **`tools/triage_agent.py`** |
| **Triage API endpoints** | **Mukul Ray** | **`backend/app.py` — `/api/triage/*`** |
| **Insurance agent · cascade design · claim assembly** | **Mukul Ray** (design) · Nikhil Sumesh / Rahul Sharma (implementation) | **`tools/insurance_agent.py`** |
| **LLM provider fallback chain · 4-provider architecture** | **Mukul Ray** | **`orchestrator/llm_provider.py`** |
| **Scalability · containerisation · ROI architecture** | **Mukul Ray** | Slides 10–12, `railway.toml` |
| Insurance loss analytics · leg history aggregation | Nikhil Sumesh | `tools/insurance_agent.py` — `_compute_loss_breakdown`, `_aggregate_leg_history` |

---

## Notes on git attribution

This project was developed under time pressure across shared machines. Several contributions
were committed under a teammate's git config after code handoff via branches. File-level
docstrings reflect original authorship where it differs from git blame.
