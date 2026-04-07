# AI Cargo Monitoring -- System Architecture

## Overview

A hybrid risk scoring engine for pharmaceutical cold-chain cargo monitoring.
Combines deterministic rule-based checks with predictive ML to produce
explainable, audit-ready spoilage-risk assessments for every telemetry window.

## Layers

```
Layer 1  IoT / Ingestion        Smart containers stream telemetry;
                                 aggregated into 25-min windows.

Layer 2  Risk Scoring Engine     Deterministic rules + XGBoost predictor
         ** CURRENT SCOPE **     fused into a single risk score & tier.

Layer 3  Agent Orchestration     Triage, rerouting, cold-storage dispatch,
                                 notification, compliance agents.

Layer 4  Human-in-the-Loop       Ops dashboard, approval workflows,
                                 audit trail viewer.

Layer 5  Downstream Cascade      Inventory forecast, patient reschedule,
                                 insurance claims, regulatory reporting.
```

## Risk Scoring Engine (Layer 2) -- Detail

```
 telemetry window
       |
       v
 +-----------------+       +--------------------+
 | Feature          |       | Product Profiles   |
 | Engineering      |<------| (WHO thresholds)   |
 +-----------------+       +--------------------+
       |
       +----------+-----------+
       |                      |
       v                      v
 +--------------+     +----------------+
 | Deterministic|     | Predictive ML  |
 | Rule Engine  |     | (XGBoost)      |
 | score: 0-1   |     | prob:  0-1     |
 +--------------+     +----------------+
       |                      |
       +----------+-----------+
                  |
                  v
         +----------------+
         | Risk Fusion    |
         | final_score    |
         | risk tier      |
         +----------------+
                  |
                  v
         +----------------+
         | Compliance Log |
         | (JSON audit)   |
         +----------------+
```

### Deterministic Rules

Product-aware threshold checks executed on every window:

| Rule               | Signal                          | Contribution |
|--------------------|---------------------------------|-------------|
| Temp breach        | avg_temp outside product range  | 0.30 / 0.60 |
| Temp trend         | slope heading toward breach     | 0.20        |
| Excursion duration | cumulative minutes out of range | 0.30        |
| Battery critical   | battery < 20%                   | 0.15        |
| High humidity      | humidity > threshold            | 0.10        |
| Delay + temp stress| delay > 120 min AND near breach | 0.25        |

Critical deterministic scores (>0.8) have veto power over ML.

### Predictive Model

- Algorithm: XGBoost classifier
- Target: binary spoilage risk in next 6 hours
- Split: by shipment_id (no temporal leakage)
- Imbalance: scale_pos_weight ~4.9
- Tuning: Optuna (PR-AUC objective)
- Explainability: SHAP values per prediction

### Fusion

```
final_score = alpha * deterministic + (1 - alpha) * ml_probability
```

alpha = 0.4 (default). Deterministic veto if det_score > 0.8.

### Risk Tiers

| Tier     | Range     | Action                                |
|----------|-----------|---------------------------------------|
| LOW      | 0.0--0.3  | Standard monitoring                   |
| MEDIUM   | 0.3--0.6  | Increased frequency, pre-alert        |
| HIGH     | 0.6--0.8  | Active intervention, notify ops       |
| CRITICAL | 0.8--1.0  | Immediate action, human escalation    |

## Data

- Source: `data/single_table.csv` (7 408 windows, 140 shipments, 6 products)
- Product specs: `data/product_profiles.json`

## Compliance

Every scored window produces a JSON audit record containing:
deterministic score, rules fired, ML probability, top SHAP features,
final score, risk tier, recommended actions, and human-approval flag.
