import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Loader2, Plus, Search } from "lucide-react";
import { api } from "../api";
import Pagination from "../components/Pagination";

const PAGE_SIZE = 10;

const STATUS_OPTIONS = [
  { value: "", label: "全部状态" },
  { value: "running", label: "执行中" },
  { value: "waiting_supplement", label: "等待补全" },
  { value: "completed", label: "已完成" },
  { value: "failed", label: "失败" },
  { value: "pending", label: "待执行" },
];

const STAGE_LABELS = {
  intake: "任务发起",
  parsing: "AI 解析",
  transforming: "参数转换",
  bdi_executing: "BDI 执行",
  monitoring: "状态跟踪",
  error_handling: "异常处理",
  testing: "测试验证",
  online: "上线调度",
};

function statusBadge(status) {
  const map = {
    running: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900/40 dark:text-indigo-200",
    waiting_supplement: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200",
    completed: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200",
    failed: "bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-200",
    pending: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
  };
  const cls = map[status] || map.pending;
  return <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>{status}</span>;
}

export default function OfflineCollectList() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState({ items: [], total: 0, total_pages: 0, page: 1, page_size: PAGE_SIZE });
  const [loading, setLoading] = useState(true);
  const [debouncedQ, setDebouncedQ] = useState("");

  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q.trim()), 400);
    return () => clearTimeout(t);
  }, [q]);

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.flows.listStatic({
        q: debouncedQ,
        status,
        category: "province",
        page,
        page_size: PAGE_SIZE,
      });
      setData(res);
    } catch (e) {
      console.error(e);
      setData({ items: [], total: 0, total_pages: 0, page: 1, page_size: PAGE_SIZE });
    } finally {
      setLoading(false);
    }
  }, [debouncedQ, status, page]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  useEffect(() => {
    setPage(1);
  }, [debouncedQ, status]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex min-w-0 flex-1 flex-col gap-2 sm:flex-row sm:items-end">
          <label className="min-w-0 flex-1 text-sm font-medium text-slate-700 dark:text-slate-200">
            检索
            <span className="relative mt-1 block">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                className="w-full rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-3 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-800 dark:text-white"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="任务名称或表名"
              />
            </span>
          </label>
          <label className="text-sm font-medium text-slate-700 dark:text-slate-200 sm:w-44">
            状态
            <select
              className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-white"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              {STATUS_OPTIONS.map((o) => (
                <option key={o.value || "all"} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <Link
          to="/offline-collect/province"
          className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-indigo-700"
        >
          <Plus className="h-4 w-4" />
          新增省分个采
        </Link>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
        {loading ? (
          <div className="flex items-center justify-center py-16 text-slate-500">
            <Loader2 className="h-8 w-8 animate-spin" />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500 dark:border-slate-800 dark:bg-slate-800/80 dark:text-slate-400">
                <tr>
                  <th className="px-4 py-3 font-medium">ID</th>
                  <th className="px-4 py-3 font-medium">任务名称</th>
                  <th className="px-4 py-3 font-medium">表名</th>
                  <th className="px-4 py-3 font-medium">状态</th>
                  <th className="px-4 py-3 font-medium">进度</th>
                  <th className="px-4 py-3 font-medium">阶段</th>
                  <th className="px-4 py-3 font-medium">创建时间</th>
                  <th className="px-4 py-3 font-medium">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {data.items.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-12 text-center text-slate-500">
                      暂无省分个采记录，请点击「新增省分个采」发起。
                    </td>
                  </tr>
                ) : (
                  data.items.map((row) => (
                    <tr key={row.id} className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40">
                      <td className="px-4 py-3 font-mono text-xs text-slate-500">#{row.id}</td>
                      <td className="max-w-[200px] truncate px-4 py-3 font-medium text-slate-900 dark:text-slate-100">
                        {row.name}
                      </td>
                      <td className="max-w-[160px] truncate px-4 py-3 text-slate-600 dark:text-slate-300">
                        {row.table_name}
                      </td>
                      <td className="px-4 py-3">{statusBadge(row.status)}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className="h-2 w-24 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
                            <div
                              className="h-full rounded-full bg-indigo-500 transition-all"
                              style={{ width: `${Math.min(100, Math.max(0, row.progress || 0))}%` }}
                            />
                          </div>
                          <span className="text-xs text-slate-500">{row.progress ?? 0}%</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-600 dark:text-slate-300">
                        {STAGE_LABELS[row.stage] || row.stage || "—"}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-500">
                        {row.created_at ? row.created_at.replace("T", " ").slice(0, 19) : "—"}
                      </td>
                      <td className="px-4 py-3">
                        <Link
                          to={`/offline-collect/province?id=${row.id}`}
                          className="text-indigo-600 hover:underline dark:text-indigo-400"
                        >
                          查看
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
        {!loading && data.total_pages > 0 ? (
          <div className="border-t border-slate-100 p-4 dark:border-slate-800">
            <Pagination
              page={data.page}
              totalPages={data.total_pages}
              total={data.total}
              pageSize={data.page_size || PAGE_SIZE}
              onPageChange={setPage}
            />
          </div>
        ) : null}
      </div>
    </div>
  );
}
