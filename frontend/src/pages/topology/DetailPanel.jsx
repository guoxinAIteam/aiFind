import React from "react";
import { X } from "lucide-react";

// 阶段 B 仅显示节点基本信息；阶段 C 会接入 /api/topology/nodes/{key} 拉取调用/事件/BDI 绑定。
export default function DetailPanel({ node, onClose }) {
  if (!node) return null;
  return (
    <aside className="pointer-events-auto absolute right-4 top-[130px] z-10 max-h-[calc(100vh-160px)] w-[320px] overflow-auto rounded-2xl border border-slate-700/60 bg-slate-900/80 p-4 text-slate-100 shadow-2xl backdrop-blur-md">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <div className="text-[10px] uppercase tracking-widest text-slate-400">
            Layer {node.layer} · {node.kind}
          </div>
          <div className="text-sm font-semibold text-white">{node.label}</div>
          <div className="text-[11px] text-slate-400">{node.key}</div>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-white"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <Metric label="状态" value={node.status} />
        <Metric label="活跃任务" value={node.metrics?.active_tasks ?? 0} />
        <Metric label="近 24h 调用" value={node.metrics?.calls ?? 0} />
        <Metric label="失败次数" value={node.metrics?.fail ?? 0} />
        <Metric label="平均延迟 ms" value={node.metrics?.avg_latency_ms ?? 0} />
        <Metric label="未处理告警" value={node.alerts ?? 0} />
        {node.metrics?.cpu ? <Metric label="CPU" value={`${node.metrics.cpu}%`} /> : null}
        {node.metrics?.mem ? <Metric label="Mem" value={`${node.metrics.mem}%`} /> : null}
      </div>
      <div className="mt-3 rounded-lg bg-slate-800/60 p-2 text-[11px] text-slate-300">
        节点详情（最近调用 / 事件 / BDI 绑定）将在阶段 C 接入 <code className="text-slate-400">/api/topology/nodes/{node.key}</code>
      </div>
    </aside>
  );
}

function Metric({ label, value }) {
  return (
    <div className="rounded bg-slate-800/70 px-2 py-1.5">
      <div className="text-[10px] text-slate-400">{label}</div>
      <div className="text-sm font-semibold text-white">{value}</div>
    </div>
  );
}
