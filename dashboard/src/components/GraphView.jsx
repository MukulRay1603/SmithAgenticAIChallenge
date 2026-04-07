import { useEffect, useRef, useState } from 'react';
import { useApi } from '../hooks/useApi';
import mermaid from 'mermaid';

mermaid.initialize({ startOnLoad: false, theme: 'dark', securityLevel: 'loose' });

export default function GraphView() {
  const { data: mermaidData } = useApi('/graph/mermaid');
  const { data: topology } = useApi('/graph/topology');
  const chartRef = useRef(null);
  const [tab, setTab] = useState('orchestrator');

  useEffect(() => {
    if (mermaidData?.mermaid && chartRef.current && tab === 'orchestrator') {
      chartRef.current.innerHTML = '';
      mermaid.render('orch-graph', mermaidData.mermaid).then(({ svg }) => {
        chartRef.current.innerHTML = svg;
      }).catch(() => {});
    }
  }, [mermaidData, tab]);

  const SYSTEM_MERMAID = `graph TB
    subgraph L1["Layer 1: IoT & Ingestion"]
      sensors["Smart Containers\\n(temp, humidity, shock, GPS)"]
      ingest["Window Aggregation\\n(25-min windows)"]
      sensors --> ingest
    end

    subgraph L2["Layer 2: Risk Scoring Engine"]
      features["Feature Engineering\\n(14 derived features)"]
      det["Deterministic Rules\\n(7 product-aware rules)"]
      ml["XGBoost Predictor\\n(Optuna-tuned, SHAP)"]
      fusion["Risk Fusion\\n(alpha-blend + veto)"]
      features --> det
      features --> ml
      det --> fusion
      ml --> fusion
    end

    subgraph L3["Layer 3: Orchestration Agent"]
      interpret["Interpret Risk"]
      plan_node["Generate Plan"]
      reflect_node["Self-Critique"]
      revise_node["Revise Plan"]
      exec_node["Execute Tools"]
      output_node["Compile Decision"]
      interpret --> plan_node
      plan_node --> reflect_node
      reflect_node -->|"has gaps"| revise_node
      reflect_node -->|"plan OK"| exec_node
      revise_node --> exec_node
      exec_node --> output_node
    end

    subgraph L4["Layer 4: Agent Tools"]
      t_route["Route Agent"]
      t_cold["Cold Storage"]
      t_notify["Notification"]
      t_comply["Compliance"]
      t_sched["Scheduling"]
      t_insure["Insurance"]
      t_triage["Triage"]
      t_approve["Approval"]
    end

    subgraph L5["Layer 5: Human-in-the-Loop"]
      dashboard["Ops Dashboard"]
      approval_q["Approval Queue"]
    end

    ingest --> features
    fusion --> interpret
    exec_node --> t_route
    exec_node --> t_cold
    exec_node --> t_notify
    exec_node --> t_comply
    exec_node --> t_insure
    exec_node --> t_approve
    t_approve --> approval_q
    output_node --> dashboard
    approval_q --> dashboard`;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">System Architecture & Agent Graph</h1>

      <div className="flex gap-2">
        {['system', 'orchestrator'].map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
              tab === t ? 'bg-slate-800 text-white' : 'bg-white border border-slate-300 text-slate-600 hover:bg-slate-100'
            }`}>
            {t === 'system' ? 'Full System (5 Layers)' : 'Orchestration Agent'}
          </button>
        ))}
      </div>

      {tab === 'system' && (
        <SystemGraph mermaidStr={SYSTEM_MERMAID} />
      )}

      {tab === 'orchestrator' && (
        <div className="bg-slate-900 rounded-xl p-6 shadow-lg overflow-x-auto">
          <div ref={chartRef} className="flex justify-center min-h-[300px]" />
          {!mermaidData && <p className="text-slate-400 text-center">Loading graph...</p>}
        </div>
      )}

      {topology && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <h2 className="text-sm font-semibold text-slate-600 mb-3">Layer Summary</h2>
          <div className="grid grid-cols-5 gap-3">
            {topology.layers.map(layer => (
              <div key={layer.id} className="border border-slate-200 rounded-lg p-3">
                <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">{layer.id}</p>
                <p className="text-sm font-semibold mt-1">{layer.name}</p>
                <div className="mt-2 space-y-1">
                  {layer.nodes.map(n => (
                    <span key={n.id} className="inline-block bg-slate-100 text-slate-700 px-2 py-0.5 rounded text-xs mr-1 mb-1">
                      {n.label}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function SystemGraph({ mermaidStr }) {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current) {
      ref.current.innerHTML = '';
      mermaid.render('sys-graph-' + Date.now(), mermaidStr).then(({ svg }) => {
        ref.current.innerHTML = svg;
      }).catch(() => {});
    }
  }, [mermaidStr]);
  return (
    <div className="bg-slate-900 rounded-xl p-6 shadow-lg overflow-x-auto">
      <div ref={ref} className="flex justify-center min-h-[400px]" />
    </div>
  );
}
