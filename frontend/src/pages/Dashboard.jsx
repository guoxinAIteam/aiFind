import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  Layers,
  Loader2,
  TrendingUp,
  Zap,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api";

function formatTimeHm(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function StatCard({ icon: Icon, label, value, suffix, borderClass, iconClass }) {
  return (
    <div
      className={`flex items-center gap-4 rounded-xl border border-zinc-200/80 bg-white p-5 shadow-sm dark:border-zinc-700 dark:bg-zinc-900 ${borderClass}`}
    >
      <div
        className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-lg ${iconClass}`}
      >
        <Icon className="h-6 w-6" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">{label}</p>
        <p className="truncate text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          {value}
          {suffix != null ? (
            <span className="text-lg font-medium text-zinc-500 dark:text-zinc-400">
              {suffix}
            </span>
          ) : null}
        </p>
      </div>
    </div>
  );
}

function SeverityBadge({ severity }) {
  const s = (severity || "info").toLowerCase();
  const map = {
    critical: "bg-red-100 text-red-800 ring-red-600/20 dark:bg-red-950/50 dark:text-red-200",
    warning: "bg-amber-100 text-amber-900 ring-amber-600/20 dark:bg-amber-950/40 dark:text-amber-100",
    info: "bg-blue-100 text-blue-800 ring-blue-600/20 dark:bg-blue-950/50 dark:text-blue-200",
  };
  const cls = map[s] || map.info;
  const label =
    s === "critical" ? "严重" : s === "warning" ? "警告" : "信息";
  return (
    <span
      className={`inline-flex shrink-0 rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${cls}`}
    >
      {label}
    </span>
  );
}

function TaskStatusBadge({ status }) {
  const st = (status || "pending").toLowerCase();
  const base = "inline-flex rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset";
  if (st === "completed") {
    return (
      <span className={`${base} bg-emerald-100 text-emerald-800 ring-emerald-600/20 dark:bg-emerald-950/50 dark:text-emerald-200`}>
        已完成
      </span>
    );
  }
  if (st === "running") {
    return (
      <span
        className={`${base} animate-pulse bg-sky-100 text-sky-800 ring-sky-600/20 dark:bg-sky-950/50 dark:text-sky-200`}
      >
        运行中
      </span>
    );
  }
  if (st === "failed") {
    return (
      <span className={`${base} bg-red-100 text-red-800 ring-red-600/20 dark:bg-red-950/50 dark:text-red-200`}>
        失败
      </span>
    );
  }
  return (
    <span className={`${base} bg-zinc-100 text-zinc-700 ring-zinc-600/20 dark:bg-zinc-800 dark:text-zinc-300`}>
      待执行
    </span>
  );
}

export default function Dashboard() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [metricsRaw, setMetricsRaw] = useState([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [dash, m] = await Promise.all([
          api.dashboard(),
          api.monitor.metrics("Flink"),
        ]);
        if (!cancelled) {
          setDashboard(dash);
          setMetricsRaw(Array.isArray(m) ? m : []);
        }
      } catch (e) {
        if (!cancelled) setError(e?.message || "加载失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const chartData = useMemo(() => {
    const rows = [...metricsRaw].reverse();
    return rows.map((r) => ({
      timeLabel: formatTimeHm(r.recorded_at),
      value: Number(r.metric_value ?? r.value ?? 0),
      recorded_at: r.recorded_at,
    }));
  }, [metricsRaw]);

  const stats = dashboard?.stats ?? {};

  if (loading) {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center gap-3 text-zinc-500">
        <Loader2 className="h-10 w-10 animate-spin text-blue-600" />
        <p className="text-sm">正在加载仪表盘…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
        {error}
      </div>
    );
  }

  const recentTasks = dashboard?.recent_tasks ?? [];
  const recentEvents = dashboard?.recent_events ?? [];

  return (
    <div className="mx-auto max-w-7xl space-y-8 px-4 py-8 sm:px-6 lg:px-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          智能采集 · 仪表盘
        </h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          任务概览、系统指标与最近告警
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={Layers}
          label="任务总数"
          value={stats.total_tasks ?? 0}
          borderClass="border-l-4 border-l-blue-500"
          iconClass="bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300"
        />
        <StatCard
          icon={Activity}
          label="运行中"
          value={stats.running ?? 0}
          borderClass="border-l-4 border-l-emerald-500"
          iconClass="bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
        />
        <StatCard
          icon={TrendingUp}
          label="成功率"
          value={stats.success_rate ?? 0}
          suffix="%"
          borderClass="border-l-4 border-l-amber-500"
          iconClass="bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200"
        />
        <StatCard
          icon={Zap}
          label="自动化率"
          value={stats.automation_rate ?? 0}
          suffix="%"
          borderClass="border-l-4 border-l-violet-500"
          iconClass="bg-violet-100 text-violet-800 dark:bg-violet-950 dark:text-violet-200"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <section className="rounded-xl border border-zinc-200/80 bg-white p-5 shadow-sm dark:border-zinc-700 dark:bg-zinc-900 lg:col-span-2">
          <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-50">
            系统指标趋势
          </h2>
          <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">
            Flink 吞吐（来源：monitor.metrics）
          </p>
          <div className="mt-4 h-72 w-full">
            {chartData.length === 0 ? (
              <div className="flex h-full items-center justify-center text-sm text-zinc-400">
                暂无指标数据
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="dashThroughput" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-zinc-200 dark:stroke-zinc-700" />
                  <XAxis
                    dataKey="timeLabel"
                    tick={{ fontSize: 11, fill: "currentColor" }}
                    className="text-zinc-500"
                  />
                  <YAxis tick={{ fontSize: 11, fill: "currentColor" }} className="text-zinc-500" />
                  <Tooltip
                    contentStyle={{
                      borderRadius: "0.5rem",
                      border: "1px solid rgb(228 228 231)",
                      fontSize: "12px",
                    }}
                    labelFormatter={(_, payload) =>
                      payload?.[0]?.payload?.recorded_at
                        ? formatTimeHm(payload[0].payload.recorded_at)
                        : ""
                    }
                  />
                  <Area
                    type="monotone"
                    dataKey="value"
                    stroke="#2563eb"
                    strokeWidth={2}
                    fill="url(#dashThroughput)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </section>

        <section className="rounded-xl border border-zinc-200/80 bg-white p-5 shadow-sm dark:border-zinc-700 dark:bg-zinc-900">
          <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-50">
            最近告警
          </h2>
          <ul className="mt-4 max-h-72 space-y-3 overflow-y-auto pr-1">
            {recentEvents.length === 0 ? (
              <li className="text-sm text-zinc-400">暂无事件</li>
            ) : (
              recentEvents.map((ev) => (
                <li
                  key={ev.id}
                  className="rounded-lg border border-zinc-100 bg-zinc-50/80 p-3 dark:border-zinc-800 dark:bg-zinc-800/40"
                >
                  <div className="flex items-start justify-between gap-2">
                    <SeverityBadge severity={ev.severity} />
                    <span className="shrink-0 text-xs text-zinc-400">
                      {formatTimeHm(ev.created_at)}
                    </span>
                  </div>
                  <p className="mt-2 text-sm font-medium text-zinc-800 dark:text-zinc-100">
                    {ev.title || ev.event_type || "事件"}
                  </p>
                </li>
              ))
            )}
          </ul>
        </section>
      </div>

      <section className="rounded-xl border border-zinc-200/80 bg-white p-5 shadow-sm dark:border-zinc-700 dark:bg-zinc-900">
        <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-50">
          最近采集任务
        </h2>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="border-b border-zinc-200 text-xs font-medium uppercase tracking-wide text-zinc-500 dark:border-zinc-700 dark:text-zinc-400">
                <th className="pb-3 pr-4">任务名称</th>
                <th className="pb-3 pr-4">目标表</th>
                <th className="pb-3 pr-4">状态</th>
                <th className="pb-3 pr-4">进度</th>
                <th className="pb-3">创建时间</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {recentTasks.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-zinc-400">
                    暂无任务
                  </td>
                </tr>
              ) : (
                recentTasks.map((t) => {
                  const pct = Math.min(100, Math.max(0, Number(t.progress) || 0));
                  return (
                    <tr key={t.id} className="text-zinc-800 dark:text-zinc-200">
                      <td className="py-3 pr-4 font-medium">{t.name}</td>
                      <td className="py-3 pr-4 font-mono text-xs text-zinc-600 dark:text-zinc-400">
                        {t.table_name}
                      </td>
                      <td className="py-3 pr-4">
                        <TaskStatusBadge status={t.status} />
                      </td>
                      <td className="py-3 pr-4">
                        <div className="flex items-center gap-2">
                          <div className="h-2 flex-1 max-w-[140px] overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-700">
                            <div
                              className="h-full rounded-full bg-blue-600 transition-all dark:bg-blue-500"
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                          <span className="tabular-nums text-xs text-zinc-500">{pct}%</span>
                        </div>
                      </td>
                      <td className="py-3 text-xs text-zinc-500">
                        {t.created_at || "—"}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
