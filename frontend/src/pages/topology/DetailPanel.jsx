import React, { useEffect, useState } from "react";
import { X, RefreshCw, AlertTriangle, ArrowRight } from "lucide-react";
import { api } from "../../api";

// 节点详情侧栏：展示 snapshot 中的实时指标 + 近 20 条 AgentInvocation + 近 10 条事件；
// 若是 BDI 阶段节点再展示最近 10 条 BdiTaskBinding。节点切换/每 5s 自动刷新。
export default function DetailPanel({ node, onClose }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    if (!node) {
      setDetail(null);
      return;
    }
    let alive = true;
    const fetchDetail = async () => {
      setLoading(true);
      setErr(null);
      try {
        const d = await api.topology.nodeDetail(node.key);
        if (alive) setDetail(d);
      } catch (e) {
        if (alive) setErr(String(e));
      } finally {
        if (alive) setLoading(false);
      }
    };
    fetchDetail();
    const t = setInterval(fetchDetail, 5000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [node]);

  if (!node) return null;

  return (
    <aside className="pointer-events-auto absolute right-4 top-[130px] z-10 max-h-[calc(100vh-170px)] w-[360px] overflow-auto rounded-2xl border border-slate-700/60 bg-slate-900/85 p-4 text-slate-100 shadow-2xl backdrop-blur-md">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <div className="text-[10px] uppercase tracking-widest text-slate-400">
            Layer {node.layer} · {node.kind}
          </div>
          <div className="text-sm font-semibold text-white">{node.label}</div>
          <div className="text-[11px] text-slate-400">{node.key}</div>
        </div>
        <div className="flex items-center gap-1">
          {loading ? (
            <RefreshCw className="h-3.5 w-3.5 animate-spin text-slate-400" />
          ) : null}
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-white"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs">
        <Metric label="状态" value={node.status} />
        <Metric label="活跃任务" value={node.metrics?.active_tasks ?? 0} />
        <Metric label="近 24h 调用" value={node.metrics?.calls ?? 0} />
        <Metric label="失败次数" value={node.metrics?.fail ?? 0} />
        <Metric label="平均延迟" value={`${node.metrics?.avg_latency_ms ?? 0} ms`} />
        <Metric label="未处理告警" value={node.alerts ?? 0} />
        {node.metrics?.cpu ? <Metric label="CPU" value={`${node.metrics.cpu}%`} /> : null}
        {node.metrics?.mem ? <Metric label="Mem" value={`${node.metrics.mem}%`} /> : null}
      </div>

      {err ? (
        <div className="mt-3 rounded bg-rose-500/15 px-2 py-1.5 text-[11px] text-rose-200">
          详情加载失败：{err}
        </div>
      ) : null}

      <Section title={`近 20 条调用 (${detail?.invocations?.length ?? 0})`}>
        {detail?.invocations?.length ? (
          <ul className="space-y-1">
            {detail.invocations.map((r) => (
              <li
                key={r.id}
                className="flex items-center justify-between gap-2 rounded bg-slate-800/60 px-2 py-1"
              >
                <span className="flex items-center gap-1 truncate">
                  <StatusDot status={r.status} />
                  <span className="text-slate-200">{r.direction}</span>
                  <ArrowRight className="h-3 w-3 text-slate-500" />
                  <span className="truncate text-slate-300">{r.tool_name || r.agent}</span>
                </span>
                <span className="shrink-0 text-[10px] text-slate-500">
                  {r.latency_ms ? `${r.latency_ms}ms` : ""}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <Empty text="暂无调用记录" />
        )}
      </Section>

      <Section title={`近 10 条事件 (${detail?.events?.length ?? 0})`}>
        {detail?.events?.length ? (
          <ul className="space-y-1">
            {detail.events.map((e) => (
              <li
                key={e.id}
                className="flex items-start gap-2 rounded bg-slate-800/60 px-2 py-1"
              >
                <SeverityIcon severity={e.severity} />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-slate-200">{e.title}</div>
                  <div className="text-[10px] text-slate-500">
                    {e.event_type} · {e.created_at?.slice(11, 19) || ""}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <Empty text="暂无告警事件" />
        )}
      </Section>

      {detail?.bdi_bindings?.length ? (
        <Section title={`关联 BDI 绑定 (${detail.bdi_bindings.length})`}>
          <ul className="space-y-1">
            {detail.bdi_bindings.map((b) => (
              <li
                key={b.id}
                className="flex items-center justify-between gap-2 rounded bg-slate-800/60 px-2 py-1"
              >
                <span className="truncate text-slate-200">
                  任务 #{b.task_id} / BDI {b.bdi_task_id || "-"}
                </span>
                <span className="shrink-0 rounded bg-slate-700/70 px-1.5 py-0.5 text-[10px] text-slate-200">
                  {b.full_status}
                </span>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}
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

function Section({ title, children }) {
  return (
    <div className="mt-3">
      <div className="mb-1 text-[10px] uppercase tracking-widest text-slate-400">
        {title}
      </div>
      <div className="text-[11px]">{children}</div>
    </div>
  );
}

function Empty({ text }) {
  return <div className="rounded bg-slate-800/40 px-2 py-1.5 text-slate-500">{text}</div>;
}

function StatusDot({ status }) {
  const color = status === "succeeded" ? "bg-emerald-400" : "bg-rose-400";
  return <span className={`h-1.5 w-1.5 rounded-full ${color}`} />;
}

function SeverityIcon({ severity }) {
  const color = severity === "critical" ? "text-rose-300" : severity === "warning" ? "text-amber-300" : "text-sky-300";
  return <AlertTriangle className={`mt-0.5 h-3 w-3 shrink-0 ${color}`} />;
}
