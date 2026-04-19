import React, { useEffect, useState } from "react";
import { Activity, AlertTriangle, CheckCircle2, Loader2, RadioTower, Gauge } from "lucide-react";

const statMeta = [
  { key: "running", label: "进行中", color: "text-sky-300", Icon: Loader2, spin: true },
  { key: "waiting", label: "等待补全", color: "text-amber-300", Icon: RadioTower },
  { key: "failed", label: "失败", color: "text-rose-300", Icon: AlertTriangle },
  { key: "completed", label: "已完成", color: "text-emerald-300", Icon: CheckCircle2 },
  { key: "alerts", label: "未处理告警", color: "text-orange-300", Icon: Activity },
  { key: "tps", label: "调用 TPS", color: "text-indigo-300", Icon: Gauge, suffix: "" },
];

const CONN_LABEL = {
  idle: { label: "待连接", color: "bg-slate-500" },
  connecting: { label: "连接中", color: "bg-amber-500 animate-pulse" },
  open: { label: "实时推送", color: "bg-emerald-500" },
  fallback: { label: "轮询降级", color: "bg-sky-500" },
  error: { label: "重连中", color: "bg-rose-500 animate-pulse" },
};

export default function Hud({ stats, connState, paused, onTogglePause, events }) {
  const conn = CONN_LABEL[connState] || CONN_LABEL.idle;
  const totalTasks = stats?.total_tasks ?? "-";

  return (
    <>
      {/* 顶部中央标题条 */}
      <div className="pointer-events-none absolute left-1/2 top-4 -translate-x-1/2">
        <div className="pointer-events-auto inline-flex items-center gap-3 rounded-full border border-slate-700/60 bg-slate-900/60 px-5 py-2 backdrop-blur-md">
          <span className="h-2 w-2 rounded-full bg-indigo-400 shadow-[0_0_10px_rgba(99,102,241,0.8)]" />
          <span className="text-sm font-semibold tracking-wide text-white">
            aiFind 全景大屏 · 实时采集与同步
          </span>
          <span className={`inline-flex items-center gap-1 rounded-full bg-slate-800/70 px-2 py-0.5 text-[11px] text-slate-200`}>
            <span className={`inline-block h-1.5 w-1.5 rounded-full ${conn.color}`} />
            {conn.label}
          </span>
        </div>
      </div>

      {/* 右上角 HUD */}
      <div className="pointer-events-auto absolute right-4 top-4 w-[280px] rounded-2xl border border-slate-700/60 bg-slate-900/70 p-4 text-slate-100 shadow-2xl backdrop-blur-md">
        <div className="mb-3 flex items-center justify-between">
          <div className="text-xs uppercase tracking-widest text-slate-400">运行态势</div>
          <button
            type="button"
            onClick={onTogglePause}
            className="rounded border border-slate-600 px-2 py-0.5 text-[10px] text-slate-300 hover:bg-slate-800"
            title="暂停/恢复粒子动画（P）"
          >
            {paused ? "▶ 恢复" : "⏸ 暂停"}
          </button>
        </div>
        <div className="mb-3 text-2xl font-bold tracking-tight">
          {totalTasks}
          <span className="ml-2 text-xs font-medium text-slate-400">累计任务</span>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {statMeta.map(({ key, label, color, Icon, spin, suffix }) => {
            const v = stats?.[key];
            const display = v === undefined || v === null ? "-" : v;
            return (
              <div
                key={key}
                className="rounded-lg bg-slate-800/70 px-2.5 py-2"
              >
                <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-slate-400">
                  <Icon className={`h-3 w-3 ${color} ${spin && key === "running" && (v ?? 0) > 0 ? "animate-spin" : ""}`} />
                  {label}
                </div>
                <div className={`mt-0.5 text-lg font-semibold ${color}`}>
                  {display}
                  {suffix ? <span className="ml-0.5 text-xs text-slate-400">{suffix}</span> : null}
                </div>
              </div>
            );
          })}
        </div>
        {stats?.updated_at ? (
          <div className="mt-3 text-right text-[10px] text-slate-500">
            更新：{new Date(stats.updated_at).toLocaleTimeString()}
          </div>
        ) : null}
      </div>

      {/* 底部事件滚动条 */}
      <EventTicker events={events} />
    </>
  );
}

function EventTicker({ events }) {
  // 每 4s 切换到下一条（仅展示最近 10 条循环）
  const [idx, setIdx] = useState(0);
  useEffect(() => {
    setIdx(0);
  }, [events?.length]);
  useEffect(() => {
    if (!events?.length) return;
    const t = setInterval(() => {
      setIdx((v) => (v + 1) % Math.min(events.length, 10));
    }, 4000);
    return () => clearInterval(t);
  }, [events]);

  if (!events?.length) {
    return (
      <div className="pointer-events-none absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full border border-slate-700/40 bg-slate-900/50 px-4 py-1.5 text-[11px] text-slate-400 backdrop-blur">
        暂无实时事件 · SSE 持续监听中
      </div>
    );
  }
  const cur = events[Math.min(idx, events.length - 1)];
  const sevColor = {
    critical: "text-rose-300",
    warning: "text-amber-300",
    info: "text-sky-300",
  }[cur.severity] || "text-slate-200";
  return (
    <div className="pointer-events-auto absolute bottom-4 left-1/2 w-[min(900px,90%)] -translate-x-1/2 overflow-hidden rounded-full border border-slate-700/60 bg-slate-900/70 px-4 py-1.5 text-xs text-slate-200 shadow-xl backdrop-blur">
      <div key={cur.id} className="flex animate-[fadeIn_0.3s_ease] items-center gap-3">
        <span className={`font-semibold ${sevColor}`}>{(cur.severity || "info").toUpperCase()}</span>
        <span className="text-slate-400">[{cur.source_system || "-"}]</span>
        <span className="flex-1 truncate">{cur.title}</span>
        <span className="text-[10px] text-slate-500">
          {Math.min(idx + 1, events.length)}/{Math.min(events.length, 10)}
        </span>
      </div>
    </div>
  );
}
