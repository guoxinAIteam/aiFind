import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Circle,
  GitBranch,
  Layers,
  Loader2,
  Play,
  Plus,
  XCircle,
  Zap,
} from "lucide-react";
import { api } from "../api";

const INPUT_CLASS =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-800 dark:text-white";

const DEFAULT_FORM = {
  name: "",
  table_name: "",
  task_type: "full+incremental",
  cluster: "hh-fed-sub18",
  namespace: "ctg363566671677_hh_fed_sub19_cjzh_cbss_hbase_lb19",
  tenant: "ctg363566671677",
  workspace: "hh_fed_sub18_cjzh_cbss_lb18",
  work_group: "cjzh_cbss_lb18_wg",
  zk_hosts: "10.177.138.67,10.177.138.68,10.177.138.69",
  zk_parent: "/hbasesub19",
  zk_port: 2181,
  kafka_brokers:
    "10.177.64.59:32001,10.177.64.58:32001,10.177.105.150:32003,10.177.105.152:32010,10.177.38.124:32003,10.177.38.118:32005",
  kafka_topic: "tprds-dc-i-prods-new",
  field_count: 22,
  field_list: "",
  pk_indexes: "0,4",
  file_size_gb: 1,
  compression: "gz",
  init_date: "",
  interface_id: "",
  date_field_indexes: "",
  mc_table_name: "",
};

function normalizeListResponse(raw, page, pageSize) {
  if (Array.isArray(raw)) {
    const total = raw.length;
    const totalPages = Math.max(1, Math.ceil(total / pageSize));
    const safePage = Math.min(page, totalPages);
    const start = (safePage - 1) * pageSize;
    return {
      items: raw.slice(start, start + pageSize),
      total,
      page: safePage,
      page_size: pageSize,
      total_pages: totalPages,
    };
  }
  const items = raw?.items ?? [];
  const total = Number(raw?.total) || 0;
  const totalPages = Math.max(1, Number(raw?.total_pages) || Math.ceil(total / pageSize) || 1);
  return {
    items,
    total,
    page: Number(raw?.page) || page,
    page_size: Number(raw?.page_size) || pageSize,
    total_pages: totalPages,
  };
}

function Pagination({ page, totalPages, onPageChange }) {
  const pages = useMemo(() => {
    if (totalPages <= 5) {
      return Array.from({ length: totalPages }, (_, i) => i + 1);
    }
    let start = Math.max(1, page - 2);
    let end = Math.min(totalPages, start + 4);
    if (end - start < 4) start = Math.max(1, end - 4);
    return Array.from({ length: end - start + 1 }, (_, i) => start + i);
  }, [page, totalPages]);

  return (
    <nav
      className="flex flex-wrap items-center justify-center gap-1 sm:justify-end"
      aria-label="分页"
    >
      <button
        type="button"
        disabled={page <= 1}
        onClick={() => onPageChange(page - 1)}
        className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:pointer-events-none disabled:opacity-40 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
      >
        上一页
      </button>
      {pages.map((p) => (
        <button
          key={p}
          type="button"
          onClick={() => onPageChange(p)}
          className={
            p === page
              ? "min-w-[2.25rem] rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white shadow-sm"
              : "min-w-[2.25rem] rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
          }
        >
          {p}
        </button>
      ))}
      <button
        type="button"
        disabled={page >= totalPages}
        onClick={() => onPageChange(page + 1)}
        className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:pointer-events-none disabled:opacity-40 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
      >
        下一页
      </button>
    </nav>
  );
}

function TaskStatusBadge({ status }) {
  const st = (status || "pending").toLowerCase();
  const base =
    "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset";
  if (st === "completed") {
    return (
      <span
        className={`${base} bg-emerald-100 text-emerald-800 ring-emerald-600/20 dark:bg-emerald-950/50 dark:text-emerald-200`}
      >
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
      <span
        className={`${base} bg-red-100 text-red-800 ring-red-600/20 dark:bg-red-950/50 dark:text-red-200`}
      >
        失败
      </span>
    );
  }
  return (
    <span
      className={`${base} bg-slate-100 text-slate-600 ring-slate-500/20 dark:bg-slate-800 dark:text-slate-300`}
    >
      待执行
    </span>
  );
}

function StepHeaderStatusIcon({ status }) {
  const s = (status || "pending").toLowerCase();
  if (s === "completed") {
    return <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-600 dark:text-emerald-400" />;
  }
  if (s === "running") {
    return <Loader2 className="h-5 w-5 shrink-0 animate-spin text-blue-600 dark:text-blue-400" />;
  }
  if (s === "failed") {
    return <XCircle className="h-5 w-5 shrink-0 text-red-600 dark:text-red-400" />;
  }
  return <Circle className="h-5 w-5 shrink-0 text-slate-400" />;
}

function AutomationBadge({ automation }) {
  const a = (automation || "manual").toLowerCase();
  if (a === "auto") {
    return (
      <span className="inline-flex items-center gap-0.5 rounded-md bg-emerald-100 px-1.5 py-0.5 text-[10px] font-medium text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-200">
        <Zap className="h-3 w-3" />
        自动
      </span>
    );
  }
  if (a === "semi-auto") {
    return (
      <span className="rounded-md bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
        半自动
      </span>
    );
  }
  return (
    <span className="rounded-md bg-red-100 px-1.5 py-0.5 text-[10px] font-medium text-red-800 dark:bg-red-950/40 dark:text-red-200">
      手动
    </span>
  );
}

function OperationTypeBadge({ type }) {
  const t = (type || "manual").toLowerCase();
  const base = "rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide";
  if (t === "auto") {
    return <span className={`${base} bg-emerald-100 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-200`}>auto</span>;
  }
  if (t === "semi-auto") {
    return <span className={`${base} bg-amber-100 text-amber-900 dark:bg-amber-950/40 dark:text-amber-100`}>semi</span>;
  }
  return <span className={`${base} bg-red-100 text-red-800 dark:bg-red-950/40 dark:text-red-200`}>manual</span>;
}

function OperationStatusIndicator({ displayStatus }) {
  const s = (displayStatus || "pending").toLowerCase();
  if (s === "confirmed") {
    return <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400" aria-label="已确认" />;
  }
  if (s === "running") {
    return <Loader2 className="h-4 w-4 animate-spin text-blue-600 dark:text-blue-400" aria-label="执行中" />;
  }
  return <Circle className="h-4 w-4 text-slate-400" aria-label="待处理" />;
}

function ProgressBar({ value }) {
  const pct = Math.min(100, Math.max(0, Number(value) || 0));
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
        <div
          className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-blue-600 transition-all dark:from-indigo-400 dark:to-blue-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-10 shrink-0 text-right text-xs tabular-nums text-slate-500 dark:text-slate-400">
        {pct}%
      </span>
    </div>
  );
}

function CollapsibleSection({ id, title, open, onToggle, children }) {
  return (
    <fieldset className="rounded-xl border border-slate-200 bg-slate-50/80 dark:border-slate-700 dark:bg-slate-900/40">
      <button
        type="button"
        onClick={() => onToggle(id)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left"
      >
        <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">{title}</span>
        <span className="flex shrink-0 items-center text-slate-500">
          {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </span>
      </button>
      {open ? <div className="border-t border-slate-200 px-4 pb-4 pt-2 dark:border-slate-700">{children}</div> : null}
    </fieldset>
  );
}

function normalizeOperations(step) {
  const raw = step.operations ?? step.sub_steps ?? [];
  if (!Array.isArray(raw)) return [];
  return raw.map((item, i) => {
    if (typeof item === "string") {
      return {
        id: `${step.step_order}.${i + 1}`,
        name: item,
        type: "manual",
        command: null,
        output_template: null,
        confirm_required: true,
        status: "pending",
      };
    }
    return {
      id: item.id ?? `${step.step_order}.${i + 1}`,
      name: item.name ?? "未命名操作",
      type: item.type ?? "manual",
      command: item.command ?? null,
      output_template: item.output_template ?? null,
      confirm_required: Boolean(item.confirm_required),
      status: item.status || "pending",
    };
  });
}

function firstPendingIndex(operations) {
  return operations.findIndex((o) => o.status === "pending");
}

function operationDisplayStatus(step, operations, op, opIndex) {
  if (op.status === "confirmed") return "confirmed";
  const fp = firstPendingIndex(operations);
  if (step.status === "running" && opIndex === fp && fp >= 0) return "running";
  return "pending";
}

export default function FlowManager() {
  const pageSize = 10;
  const [page, setPage] = useState(1);
  const [listData, setListData] = useState({
    items: [],
    total: 0,
    total_pages: 1,
  });
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState(null);

  const [expandedIds, setExpandedIds] = useState(() => new Set());
  const [details, setDetails] = useState({});
  const [detailLoading, setDetailLoading] = useState({});
  const [detailErrors, setDetailErrors] = useState({});
  const [confirmingKey, setConfirmingKey] = useState(null);
  const [executeLoadingId, setExecuteLoadingId] = useState(null);

  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState(() => ({ ...DEFAULT_FORM }));
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);

  const [sectionOpen, setSectionOpen] = useState(() => ({
    basic: true,
    cluster: true,
    hbase: false,
    kafka: false,
    schema: false,
    export: false,
  }));

  const toggleSection = (id) => {
    setSectionOpen((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const loadList = useCallback(async () => {
    setListError(null);
    const raw = await api.flows.list({ page, page_size: pageSize });
    const norm = normalizeListResponse(raw, page, pageSize);
    setListData({
      items: norm.items,
      total: norm.total,
      total_pages: norm.total_pages,
    });
    if (norm.page !== page) setPage(norm.page);
  }, [page]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setListLoading(true);
      try {
        await loadList();
      } catch (e) {
        if (!cancelled) setListError(e?.message || "加载任务列表失败");
      } finally {
        if (!cancelled) setListLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loadList]);

  const refreshTaskDetail = async (taskId) => {
    setDetailLoading((d) => ({ ...d, [taskId]: true }));
    setDetailErrors((d) => ({ ...d, [taskId]: null }));
    try {
      const d = await api.flows.get(taskId);
      setDetails((prev) => ({ ...prev, [taskId]: d }));
    } catch (e) {
      setDetailErrors((prev) => ({
        ...prev,
        [taskId]: e?.message || "刷新详情失败",
      }));
    } finally {
      setDetailLoading((d) => ({ ...d, [taskId]: false }));
    }
  };

  const toggleExpand = async (taskId) => {
    const wasOpen = expandedIds.has(taskId);
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(taskId)) next.delete(taskId);
      else next.add(taskId);
      return next;
    });

    if (!wasOpen && !details[taskId]) {
      setDetailLoading((d) => ({ ...d, [taskId]: true }));
      setDetailErrors((d) => ({ ...d, [taskId]: null }));
      try {
        const d = await api.flows.get(taskId);
        setDetails((prev) => ({ ...prev, [taskId]: d }));
      } catch (e) {
        setDetailErrors((prev) => ({
          ...prev,
          [taskId]: e?.message || "加载详情失败",
        }));
      } finally {
        setDetailLoading((d) => ({ ...d, [taskId]: false }));
      }
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setFormError(null);
    setSubmitting(true);
    try {
      const formData = {
        name: form.name.trim(),
        table_name: form.table_name.trim(),
        task_type: form.task_type,
        cluster: form.cluster.trim(),
        namespace: form.namespace.trim(),
        tenant: form.tenant.trim(),
        workspace: form.workspace.trim(),
        work_group: form.work_group.trim(),
        zk_hosts: form.zk_hosts.trim(),
        zk_parent: form.zk_parent.trim(),
        zk_port: Number(form.zk_port) || 2181,
        kafka_brokers: form.kafka_brokers.trim(),
        kafka_topic: form.kafka_topic.trim(),
        field_count: Number(form.field_count) || 22,
        field_list: form.field_list.trim(),
        pk_indexes: form.pk_indexes.trim(),
        file_size_gb: Number(form.file_size_gb) || 1,
        compression: form.compression,
        init_date: form.init_date.trim(),
        interface_id: form.interface_id.trim(),
        date_field_indexes: form.date_field_indexes.trim(),
        mc_table_name: form.mc_table_name.trim(),
      };
      await api.flows.create(formData);
      setModalOpen(false);
      setForm({ ...DEFAULT_FORM });
      setPage(1);
      await loadList();
    } catch (err) {
      setFormError(err?.message || "创建失败");
    } finally {
      setSubmitting(false);
    }
  };

  const handleExecute = async (taskId) => {
    setExecuteLoadingId(taskId);
    setDetailErrors((prev) => ({ ...prev, [taskId]: null }));
    try {
      await api.flows.execute(taskId);
      await loadList();
      if (expandedIds.has(taskId)) await refreshTaskDetail(taskId);
    } catch (e) {
      setDetailErrors((prev) => ({
        ...prev,
        [taskId]: e?.message || "开始执行失败",
      }));
    } finally {
      setExecuteLoadingId(null);
    }
  };

  const handleConfirmOperation = async (taskId, stepOrder, operationId) => {
    const key = `${taskId}-${stepOrder}-${operationId}`;
    setConfirmingKey(key);
    setDetailErrors((prev) => ({ ...prev, [taskId]: null }));
    try {
      await api.flows.confirmOperation(taskId, stepOrder, { operation_id: operationId });
      await loadList();
      if (expandedIds.has(taskId)) await refreshTaskDetail(taskId);
    } catch (e) {
      setDetailErrors((prev) => ({
        ...prev,
        [taskId]: e?.message || "确认操作失败",
      }));
    } finally {
      setConfirmingKey(null);
    }
  };

  const paginationFrom = listData.total === 0 ? 0 : (page - 1) * pageSize + 1;
  const paginationTo = Math.min(page * pageSize, listData.total);

  if (listLoading && listData.items.length === 0) {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center gap-3 text-slate-500 dark:text-slate-400">
        <Loader2 className="h-10 w-10 animate-spin text-indigo-600 dark:text-indigo-400" />
        <p className="text-sm">正在加载流程任务…</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-8 px-4 py-8 sm:px-6 lg:max-w-6xl lg:px-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <GitBranch className="h-8 w-8 text-indigo-600 dark:text-indigo-400" />
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-white">
                流程管理
              </h1>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
                智能订单采集平台 · 编排采集任务、查看可执行命令与分步确认
              </p>
            </div>
          </div>
        </div>
        <div className="flex flex-col items-stretch gap-3 sm:flex-row sm:items-center sm:justify-end">
          <p className="text-center text-sm text-slate-600 dark:text-slate-400 sm:text-right">
            {listData.total === 0 ? (
              "暂无任务"
            ) : (
              <>
                第 <span className="font-medium text-slate-900 dark:text-white">{page}</span> /{" "}
                <span className="font-medium text-slate-900 dark:text-white">{listData.total_pages}</span> 页 · 显示{" "}
                <span className="font-medium text-slate-900 dark:text-white">
                  {paginationFrom}–{paginationTo}
                </span>{" "}
                条，共{" "}
                <span className="font-medium text-slate-900 dark:text-white">{listData.total}</span> 条
              </>
            )}
          </p>
          <button
            type="button"
            onClick={() => {
              setFormError(null);
              setModalOpen(true);
            }}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:focus:ring-offset-slate-900"
          >
            <Plus className="h-4 w-4" />
            新建采集任务
          </button>
        </div>
      </header>

      {listError ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
          {listError}
        </div>
      ) : null}

      <div className="space-y-4">
        {listLoading && listData.items.length > 0 ? (
          <div className="flex items-center justify-center gap-2 py-6 text-sm text-slate-500">
            <Loader2 className="h-5 w-5 animate-spin text-indigo-600" />
            刷新列表…
          </div>
        ) : null}

        {!listLoading && listData.items.length === 0 ? (
          <p className="rounded-xl border border-dashed border-slate-300 bg-slate-50 py-14 text-center text-sm text-slate-500 dark:border-slate-600 dark:bg-slate-900/40 dark:text-slate-400">
            暂无任务，点击「新建采集任务」开始
          </p>
        ) : null}

        {listData.items.map((task) => {
          const open = expandedIds.has(task.id);
          const detail = details[task.id];
          const dLoading = detailLoading[task.id];
          const dErr = detailErrors[task.id];
          const steps = (detail?.steps ?? []).slice().sort((a, b) => a.step_order - b.step_order);

          return (
            <article
              key={task.id}
              className="rounded-xl border border-slate-200/90 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900/95"
            >
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0 flex-1 space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Layers className="h-4 w-4 shrink-0 text-slate-400" />
                    <h2 className="truncate text-lg font-semibold text-slate-900 dark:text-white">{task.name}</h2>
                    <TaskStatusBadge status={task.status} />
                  </div>
                  <p className="font-mono text-xs text-slate-600 dark:text-slate-400">
                    目标表：<span className="text-slate-900 dark:text-white">{task.table_name}</span>
                  </p>
                  <ProgressBar value={task.progress} />
                </div>
                <button
                  type="button"
                  onClick={() => toggleExpand(task.id)}
                  className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
                >
                  查看详情
                  {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                </button>
              </div>

              {open ? (
                <div className="mt-6 border-t border-slate-100 pt-6 dark:border-slate-800">
                  {dLoading && !detail ? (
                    <div className="flex items-center gap-2 text-sm text-slate-500">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      加载详情…
                    </div>
                  ) : null}
                  {dErr ? <p className="text-sm text-red-600 dark:text-red-400">{dErr}</p> : null}

                  {detail ? (
                    <>
                      <div className="mb-6 flex flex-wrap gap-2">
                        {task.status === "pending" ? (
                          <button
                            type="button"
                            disabled={executeLoadingId === task.id}
                            onClick={() => handleExecute(task.id)}
                            className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-emerald-700 disabled:opacity-60"
                          >
                            {executeLoadingId === task.id ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Play className="h-4 w-4" />
                            )}
                            开始执行
                          </button>
                        ) : null}
                      </div>

                      <h3 className="mb-4 text-base font-semibold text-slate-900 dark:text-white">执行流水线</h3>
                      <div className="space-y-6">
                        {steps.map((step) => {
                          const operations = normalizeOperations(step);
                          const fp = firstPendingIndex(operations);
                          return (
                            <div
                              key={step.id ?? step.step_order}
                              className="relative rounded-2xl border border-slate-200 bg-gradient-to-b from-white to-slate-50/80 p-4 shadow-sm dark:border-slate-700 dark:from-slate-900 dark:to-slate-950/80"
                            >
                              <div className="flex flex-wrap items-start gap-3">
                                <div
                                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 text-sm font-bold text-white shadow-md ring-2 ring-white dark:ring-slate-900"
                                  aria-hidden
                                >
                                  {step.step_order}
                                </div>
                                <div className="min-w-0 flex-1">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <h4 className="text-base font-semibold text-slate-900 dark:text-white">{step.name}</h4>
                                    <AutomationBadge automation={step.automation} />
                                    <StepHeaderStatusIcon status={step.status} />
                                  </div>
                                  {step.description ? (
                                    <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{step.description}</p>
                                  ) : null}
                                </div>
                              </div>

                              <ul className="mt-4 space-y-4 border-t border-slate-100 pt-4 dark:border-slate-800">
                                {operations.map((op, opIndex) => {
                                  const displayStatus = operationDisplayStatus(step, operations, op, opIndex);
                                  const isFirstPending = opIndex === fp && fp >= 0;
                                  const canConfirm =
                                    task.status === "running" &&
                                    step.status === "running" &&
                                    isFirstPending &&
                                    op.status === "pending";
                                  const confirmBusy = confirmingKey === `${task.id}-${step.step_order}-${op.id}`;

                                  return (
                                    <li
                                      key={op.id ?? opIndex}
                                      className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900/60"
                                    >
                                      <div className="flex flex-wrap items-start justify-between gap-3">
                                        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
                                          <span className="inline-flex rounded-md bg-slate-100 px-2 py-0.5 font-mono text-xs font-semibold text-slate-800 dark:bg-slate-800 dark:text-slate-200">
                                            {op.id}
                                          </span>
                                          <span className="font-medium text-slate-900 dark:text-white">{op.name}</span>
                                          <OperationTypeBadge type={op.type} />
                                        </div>
                                        <OperationStatusIndicator displayStatus={displayStatus} />
                                      </div>

                                      {op.command ? (
                                        <div className="mt-3">
                                          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
                                            命令
                                          </p>
                                          <pre className="max-h-48 overflow-x-auto overflow-y-auto rounded-lg bg-slate-900 p-3 font-mono text-xs leading-relaxed text-green-400">
                                            {op.command}
                                          </pre>
                                        </div>
                                      ) : null}

                                      {op.output_template ? (
                                        <div className="mt-3">
                                          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
                                            输出 / 配置预览
                                          </p>
                                          <pre className="max-h-48 overflow-x-auto overflow-y-auto rounded-lg border-2 border-blue-400/60 bg-blue-50/80 p-3 font-mono text-xs leading-relaxed text-slate-900 dark:border-blue-500/50 dark:bg-blue-950/30 dark:text-slate-100">
                                            {op.output_template}
                                          </pre>
                                        </div>
                                      ) : null}

                                      {canConfirm ? (
                                        <div className="mt-4 flex flex-wrap gap-2">
                                          <button
                                            type="button"
                                            disabled={confirmBusy}
                                            onClick={() => handleConfirmOperation(task.id, step.step_order, op.id)}
                                            className={
                                              op.confirm_required
                                                ? "inline-flex items-center gap-2 rounded-lg bg-amber-500 px-4 py-2 text-sm font-medium text-amber-950 shadow-sm hover:bg-amber-400 disabled:opacity-60 dark:bg-amber-600 dark:text-amber-50 dark:hover:bg-amber-500"
                                                : "inline-flex items-center gap-2 rounded-lg bg-slate-200 px-4 py-2 text-sm font-medium text-slate-800 hover:bg-slate-300 disabled:opacity-60 dark:bg-slate-700 dark:text-slate-100 dark:hover:bg-slate-600"
                                            }
                                          >
                                            {confirmBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                                            {op.confirm_required ? "确认完成" : "继续"}
                                          </button>
                                        </div>
                                      ) : null}
                                    </li>
                                  );
                                })}
                              </ul>
                            </div>
                          );
                        })}
                      </div>
                    </>
                  ) : null}
                </div>
              ) : null}
            </article>
          );
        })}
      </div>

      {listData.total_pages > 1 || listData.total > 0 ? (
        <div className="flex justify-center border-t border-slate-100 pt-6 dark:border-slate-800 sm:justify-end">
          <Pagination page={page} totalPages={Math.max(1, listData.total_pages)} onPageChange={setPage} />
        </div>
      ) : null}

      {modalOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <button
            type="button"
            className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm"
            aria-label="关闭"
            onClick={() => !submitting && setModalOpen(false)}
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="flow-modal-title"
            className="relative z-10 w-full max-w-3xl rounded-2xl border border-slate-200 bg-white shadow-2xl dark:border-slate-700 dark:bg-slate-900"
          >
            <div className="border-b border-slate-100 px-6 py-4 dark:border-slate-800">
              <h2 id="flow-modal-title" className="text-lg font-semibold text-slate-900 dark:text-white">
                新建采集任务
              </h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                填写基础参数与集群配置，系统将生成可执行的流水线命令（变量已按当前表单替换）。
              </p>
            </div>
            <form onSubmit={handleCreate} className="flex max-h-[85vh] flex-col">
              <div className="max-h-[70vh] space-y-4 overflow-y-auto px-6 py-4">
                <CollapsibleSection
                  id="basic"
                  title="基础信息"
                  open={sectionOpen.basic}
                  onToggle={toggleSection}
                >
                  <div className="space-y-3">
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                      任务名称 <span className="text-red-500">*</span>
                    </label>
                    <input
                      required
                      type="text"
                      value={form.name}
                      onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                      className={INPUT_CLASS}
                    />
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                      目标表名 <span className="text-red-500">*</span>
                    </label>
                    <input
                      required
                      type="text"
                      value={form.table_name}
                      onChange={(e) => setForm((f) => ({ ...f, table_name: e.target.value }))}
                      className={INPUT_CLASS}
                    />
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">任务类型</label>
                    <select
                      value={form.task_type}
                      onChange={(e) => setForm((f) => ({ ...f, task_type: e.target.value }))}
                      className={INPUT_CLASS}
                    >
                      <option value="full+incremental">full+incremental</option>
                      <option value="incremental-only">incremental-only</option>
                    </select>
                  </div>
                </CollapsibleSection>

                <CollapsibleSection
                  id="cluster"
                  title="集群与存储"
                  open={sectionOpen.cluster}
                  onToggle={toggleSection}
                >
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="sm:col-span-2">
                      <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">集群名</label>
                      <input
                        type="text"
                        value={form.cluster}
                        onChange={(e) => setForm((f) => ({ ...f, cluster: e.target.value }))}
                        className={`mt-1 ${INPUT_CLASS}`}
                      />
                    </div>
                    <div className="sm:col-span-2">
                      <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">命名空间</label>
                      <input
                        type="text"
                        value={form.namespace}
                        onChange={(e) => setForm((f) => ({ ...f, namespace: e.target.value }))}
                        className={`mt-1 ${INPUT_CLASS}`}
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">租户 ID</label>
                      <input
                        type="text"
                        value={form.tenant}
                        onChange={(e) => setForm((f) => ({ ...f, tenant: e.target.value }))}
                        className={`mt-1 ${INPUT_CLASS}`}
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">工作空间</label>
                      <input
                        type="text"
                        value={form.workspace}
                        onChange={(e) => setForm((f) => ({ ...f, workspace: e.target.value }))}
                        className={`mt-1 ${INPUT_CLASS}`}
                      />
                    </div>
                    <div className="sm:col-span-2">
                      <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">工作组</label>
                      <input
                        type="text"
                        value={form.work_group}
                        onChange={(e) => setForm((f) => ({ ...f, work_group: e.target.value }))}
                        className={`mt-1 ${INPUT_CLASS}`}
                      />
                    </div>
                  </div>
                </CollapsibleSection>

                <CollapsibleSection id="hbase" title="HBase / ZK 配置" open={sectionOpen.hbase} onToggle={toggleSection}>
                  <div className="space-y-3">
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">ZK 地址</label>
                    <input
                      type="text"
                      value={form.zk_hosts}
                      onChange={(e) => setForm((f) => ({ ...f, zk_hosts: e.target.value }))}
                      className={INPUT_CLASS}
                    />
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">ZK 父节点</label>
                    <input
                      type="text"
                      value={form.zk_parent}
                      onChange={(e) => setForm((f) => ({ ...f, zk_parent: e.target.value }))}
                      className={INPUT_CLASS}
                    />
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">ZK 端口</label>
                    <input
                      type="number"
                      value={form.zk_port}
                      onChange={(e) => setForm((f) => ({ ...f, zk_port: e.target.value }))}
                      className={INPUT_CLASS}
                    />
                  </div>
                </CollapsibleSection>

                <CollapsibleSection id="kafka" title="Kafka 配置" open={sectionOpen.kafka} onToggle={toggleSection}>
                  <div className="space-y-3">
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">Kafka Brokers</label>
                    <textarea
                      rows={3}
                      value={form.kafka_brokers}
                      onChange={(e) => setForm((f) => ({ ...f, kafka_brokers: e.target.value }))}
                      className={INPUT_CLASS}
                    />
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">Kafka Topic</label>
                    <input
                      type="text"
                      value={form.kafka_topic}
                      onChange={(e) => setForm((f) => ({ ...f, kafka_topic: e.target.value }))}
                      className={INPUT_CLASS}
                    />
                  </div>
                </CollapsibleSection>

                <CollapsibleSection id="schema" title="表结构" open={sectionOpen.schema} onToggle={toggleSection}>
                  <div className="space-y-3">
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">字段数</label>
                    <input
                      type="number"
                      min={1}
                      value={form.field_count}
                      onChange={(e) => setForm((f) => ({ ...f, field_count: e.target.value }))}
                      className={INPUT_CLASS}
                    />
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                      字段列表（逗号分隔）
                    </label>
                    <textarea
                      rows={4}
                      placeholder="例如：COL_A,COL_B,COL_C"
                      value={form.field_list}
                      onChange={(e) => setForm((f) => ({ ...f, field_list: e.target.value }))}
                      className={INPUT_CLASS}
                    />
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">主键下标</label>
                    <input
                      type="text"
                      value={form.pk_indexes}
                      onChange={(e) => setForm((f) => ({ ...f, pk_indexes: e.target.value }))}
                      className={INPUT_CLASS}
                    />
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">文件大小 GB</label>
                    <input
                      type="number"
                      min={0.01}
                      step={0.1}
                      value={form.file_size_gb}
                      onChange={(e) => setForm((f) => ({ ...f, file_size_gb: e.target.value }))}
                      className={INPUT_CLASS}
                    />
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">压缩方式</label>
                    <select
                      value={form.compression}
                      onChange={(e) => setForm((f) => ({ ...f, compression: e.target.value }))}
                      className={INPUT_CLASS}
                    >
                      <option value="gz">gz</option>
                      <option value="none">none</option>
                    </select>
                  </div>
                </CollapsibleSection>

                <CollapsibleSection id="export" title="导出配置" open={sectionOpen.export} onToggle={toggleSection}>
                  <div className="space-y-3">
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                      初始化日期（yyyyMMdd）
                    </label>
                    <input
                      type="text"
                      placeholder="20250101"
                      value={form.init_date}
                      onChange={(e) => setForm((f) => ({ ...f, init_date: e.target.value }))}
                      className={INPUT_CLASS}
                    />
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">接口 ID</label>
                    <input
                      type="text"
                      value={form.interface_id}
                      onChange={(e) => setForm((f) => ({ ...f, interface_id: e.target.value }))}
                      className={INPUT_CLASS}
                    />
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">日期字段下标</label>
                    <input
                      type="text"
                      value={form.date_field_indexes}
                      onChange={(e) => setForm((f) => ({ ...f, date_field_indexes: e.target.value }))}
                      className={INPUT_CLASS}
                    />
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">MC 表名</label>
                    <input
                      type="text"
                      value={form.mc_table_name}
                      onChange={(e) => setForm((f) => ({ ...f, mc_table_name: e.target.value }))}
                      className={INPUT_CLASS}
                    />
                  </div>
                </CollapsibleSection>

                {formError ? <p className="text-sm text-red-600 dark:text-red-400">{formError}</p> : null}
              </div>

              <div className="flex justify-end gap-2 border-t border-slate-100 px-6 py-4 dark:border-slate-800">
                <button
                  type="button"
                  disabled={submitting}
                  onClick={() => setModalOpen(false)}
                  className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                  创建任务
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  );
}
