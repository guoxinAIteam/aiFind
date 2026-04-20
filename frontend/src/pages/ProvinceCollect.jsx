import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  AlertTriangle,
  CheckCircle2,
  Circle,
  FileSpreadsheet,
  Loader2,
  PauseCircle,
  Play,
  Sparkles,
  Upload,
  XCircle,
} from "lucide-react";
import { api } from "../api";

const INPUT =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-800 dark:text-white";

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

const STATUS_LABELS = {
  pending: "待执行",
  running: "执行中",
  completed: "已完成",
  skipped: "已跳过",
  failed: "失败",
  waiting: "等待补全",
  waiting_supplement: "等待补全",
};

function StatusIcon({ status }) {
  switch (status) {
    case "completed":
      return <CheckCircle2 className="h-5 w-5 text-emerald-500" aria-hidden />;
    case "running":
      return <Loader2 className="h-5 w-5 animate-spin text-indigo-500" aria-hidden />;
    case "failed":
      return <XCircle className="h-5 w-5 text-rose-500" aria-hidden />;
    case "skipped":
      return <PauseCircle className="h-5 w-5 text-slate-400" aria-hidden />;
    case "waiting":
    case "waiting_supplement":
      return <AlertTriangle className="h-5 w-5 text-amber-500" aria-hidden />;
    default:
      return <Circle className="h-5 w-5 text-slate-300" aria-hidden />;
  }
}

function Badge({ status }) {
  const label = STATUS_LABELS[status] || status;
  const color =
    status === "completed"
      ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300"
      : status === "running"
        ? "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300"
        : status === "failed"
          ? "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300"
          : status === "waiting" || status === "waiting_supplement"
            ? "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300"
            : status === "skipped"
              ? "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400"
              : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400";
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${color}`}>
      {label}
    </span>
  );
}

function Card({ title, subtitle, children, actions }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      {title ? (
        <header className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
              {title}
            </h3>
            {subtitle ? (
              <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{subtitle}</p>
            ) : null}
          </div>
          {actions}
        </header>
      ) : null}
      {children}
    </section>
  );
}

export default function ProvinceCollect() {
  const [searchParams] = useSearchParams();
  const [form, setForm] = useState({
    name: "",
    requirement: "",
    overrides: {},
    auto_execute: true,
  });
  const [submitting, setSubmitting] = useState(false);
  const [task, setTask] = useState(null);
  const [stream, setStream] = useState([]);
  const [supplementValues, setSupplementValues] = useState({});
  const [supplementSubmitting, setSupplementSubmitting] = useState(false);
  const [importHint, setImportHint] = useState("");
  const [error, setError] = useState("");
  const streamRef = useRef(null);
  const pollTimerRef = useRef(null);
  const docxInputRef = useRef(null);
  const xlsxInputRef = useRef(null);

  const finished = task && ["completed", "failed"].includes(task.status);

  useEffect(() => () => {
    streamRef.current?.cancel?.();
    if (pollTimerRef.current) window.clearTimeout(pollTimerRef.current);
  }, []);

  const taskIdFromUrl = searchParams.get("id");

  const appendStream = useCallback((chunk) => {
    setStream((prev) => [...prev, { at: Date.now(), ...chunk }]);
  }, []);

  const startStream = useCallback(
    async (requirement) => {
      try {
        setStream([{ at: Date.now(), type: "chunk", content: "🤖 连接 AI 解析智能体…\n" }]);
        const resp = await api.parse.stream({ requirement });
        if (!resp.ok) {
          appendStream({ type: "error", content: `连接失败: HTTP ${resp.status}` });
          return;
        }
        const reader = resp.body?.getReader();
        if (!reader) return;
        streamRef.current = reader;
        const dec = new TextDecoder();
        let buf = "";
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buf += dec.decode(value, { stream: true });
          const parts = buf.split(/\n\n/);
          buf = parts.pop() || "";
          for (const part of parts) {
            const line = part.replace(/^data:\s*/, "").trim();
            if (!line) continue;
            try {
              appendStream(JSON.parse(line));
            } catch {
              appendStream({ type: "chunk", content: line });
            }
          }
        }
      } catch (e) {
        appendStream({ type: "error", content: `流式连接异常: ${e.message || e}` });
      }
    },
    [appendStream],
  );

  const pollTask = useCallback(
    async (id) => {
      const detail = await api.flows.getStatic(id);
      setTask(detail);
      if (!["completed", "failed", "waiting_supplement"].includes(detail.status)) {
        pollTimerRef.current = window.setTimeout(() => pollTask(id), 1500);
      }
    },
    [],
  );

  useEffect(() => {
    if (!taskIdFromUrl) return;
    const id = Number(taskIdFromUrl);
    if (!Number.isFinite(id) || id <= 0) return;
    let cancelled = false;
    (async () => {
      try {
        const detail = await api.flows.getStatic(id);
        if (!cancelled) {
          setTask(detail);
          setForm((f) => ({
            ...f,
            name: detail.name || f.name,
            requirement: (detail.config_snapshot?.requirement || "").trim() || f.requirement,
          }));
          if (!["completed", "failed", "waiting_supplement"].includes(detail.status)) {
            pollTimerRef.current = window.setTimeout(() => pollTask(id), 1000);
          }
        }
      } catch (e) {
        if (!cancelled) setError(e.message || "加载任务失败");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [taskIdFromUrl, pollTask]);

  const handleDocxChange = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setError("");
    setImportHint("");
    try {
      const { text } = await api.parse.extractDocx(file);
      setForm((f) => ({
        ...f,
        requirement: f.requirement.trim()
          ? `${f.requirement.trim()}\n\n---\n\n${text || ""}`
          : text || "",
      }));
      setImportHint(`已导入 Word：${file.name}`);
    } catch (err) {
      setError(err.message || "Word 解析失败");
    }
  };

  const handleExcelImport = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || !task) return;
    setError("");
    setImportHint("");
    try {
      const res = await api.flows.supplementImportExcel(task.id, file);
      setSupplementValues((prev) => ({ ...prev, ...res.values }));
      const unk = (res.unknown_keys_in_file || []).length;
      setImportHint(
        `Excel 已匹配 ${res.matched_count} 个字段${unk ? `，${unk} 个键未在缺失清单中已忽略` : ""}`,
      );
    } catch (err) {
      setError(err.message || "Excel 导入失败");
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name.trim() || !form.requirement.trim()) {
      setError("任务名称与需求描述不能为空");
      return;
    }
    setError("");
    setSubmitting(true);
    setTask(null);
    setStream([]);
    setSupplementValues({});

    startStream(form.requirement);

    try {
      const resp = await api.flows.createStatic({
        name: form.name,
        requirement: form.requirement,
        overrides: { ...form.overrides, category: "province" },
        auto_execute: form.auto_execute,
      });
      setTask(resp);
      if (!["completed", "failed", "waiting_supplement"].includes(resp.status)) {
        pollTimerRef.current = window.setTimeout(() => pollTask(resp.id), 1000);
      }
    } catch (err) {
      setError(err.message || "创建任务失败");
    } finally {
      setSubmitting(false);
    }
  };

  const submitSupplement = async () => {
    if (!task) return;
    setSupplementSubmitting(true);
    try {
      const resp = await api.flows.supplement(task.id, supplementValues);
      setTask(resp);
      setSupplementValues({});
    } catch (e) {
      setError(e.message || "补全失败");
    } finally {
      setSupplementSubmitting(false);
    }
  };

  const steps = task?.steps || [];
  const missingFields = useMemo(() => {
    if (!task) return [];
    return (task.missing_fields || []).filter((m) => !m.confirmed_at);
  }, [task]);

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_1.2fr]">
      {/* 左侧：表单 + 阶段进度 */}
      <div className="flex min-w-0 flex-col gap-5">
        <Card
          title="省分个采 · 创建离线采集任务"
          subtitle="录入采集需求或导入 Word（.docx）提取文本后发起；BDI 离线编排自动推进"
        >
          <form className="flex flex-col gap-3" onSubmit={handleSubmit}>
            <div className="flex flex-wrap items-center gap-2">
              <input
                ref={docxInputRef}
                type="file"
                accept=".docx"
                className="hidden"
                onChange={handleDocxChange}
              />
              <button
                type="button"
                onClick={() => docxInputRef.current?.click()}
                className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                <Upload className="h-3.5 w-3.5" />
                导入 Word（.docx）
              </button>
              <span className="text-xs text-slate-500">仅解析正文与表格为纯文本，填入下方需求描述</span>
            </div>
            {importHint ? (
              <p className="text-xs text-emerald-600 dark:text-emerald-400">{importHint}</p>
            ) : null}
            <label className="text-sm font-medium text-slate-700 dark:text-slate-200">
              任务名称
              <input
                className={INPUT + " mt-1"}
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="如：SFTP→Hive 用户图层同步"
              />
            </label>
            <label className="text-sm font-medium text-slate-700 dark:text-slate-200">
              采集需求 / 接口规范描述
              <textarea
                className={INPUT + " mt-1 min-h-[140px] font-mono text-[13px]"}
                value={form.requirement}
                onChange={(e) => setForm({ ...form, requirement: e.target.value })}
                placeholder="描述源端与目标端、文件路径、表结构、分隔符等……"
              />
            </label>
            <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-200">
              <input
                type="checkbox"
                checked={form.auto_execute}
                onChange={(e) => setForm({ ...form, auto_execute: e.target.checked })}
              />
              自动推进（解析 → 转换 → BDI 执行 → 测试 → 上线）
            </label>
            {error ? (
              <div className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-600 dark:bg-rose-900/20">
                {error}
              </div>
            ) : null}
            <div className="flex gap-2">
              <button
                type="submit"
                disabled={submitting}
                className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                发起采集
              </button>
              {task ? (
                <button
                  type="button"
                  onClick={() => pollTask(task.id)}
                  className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
                >
                  刷新
                </button>
              ) : null}
            </div>
          </form>
        </Card>

        <Card title="8 阶段推进" subtitle={task ? `任务 #${task.id} — ${task.name}` : "尚未发起任务"}>
          {task ? (
            <ol className="flex flex-col gap-1">
              {steps.map((s) => (
                <li
                  key={s.step_order}
                  className="flex items-start gap-3 rounded-lg border border-slate-100 px-3 py-2 dark:border-slate-800"
                >
                  <div className="pt-0.5">
                    <StatusIcon status={s.status} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-sm font-medium text-slate-800 dark:text-slate-100">
                        阶段 {s.step_order}. {s.name}
                      </div>
                      <Badge status={s.status} />
                    </div>
                    {s.description ? (
                      <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                        {s.description}
                      </p>
                    ) : null}
                    {s.log ? (
                      <pre className="mt-1 max-h-24 overflow-auto whitespace-pre-wrap rounded bg-slate-50 px-2 py-1 text-[12px] text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                        {s.log}
                      </pre>
                    ) : null}
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-sm text-slate-500 dark:text-slate-400">创建任务后将实时显示阶段进度。</p>
          )}
        </Card>
      </div>

      {/* 右侧：流式解析 + BDI 执行 + 缺失字段交互 */}
      <div className="flex min-w-0 flex-col gap-5">
        <Card
          title="AI 解析流式输出"
          subtitle="对齐联通能开 AI 智能体 stream API，实时展示解析过程"
          actions={<Sparkles className="h-5 w-5 text-amber-500" aria-hidden />}
        >
          <div className="max-h-[280px] min-h-[120px] overflow-auto rounded-lg bg-slate-950 p-3 font-mono text-[12px] text-emerald-200">
            {stream.length === 0 ? (
              <span className="text-slate-500">等待任务发起……</span>
            ) : (
              stream.map((e, i) => (
                <div key={i} className="whitespace-pre-wrap">
                  {e.type === "final" ? (
                    <span className="text-amber-300">
                      ✅ 解析完成，结构化字段：
                      {"\n"}
                      {JSON.stringify(e.structured, null, 2)}
                    </span>
                  ) : e.type === "error" ? (
                    <span className="text-rose-300">❌ {e.content}</span>
                  ) : e.type === "done" ? (
                    <span className="text-emerald-300">🟢 解析落库 parse_id={e.parse_id}</span>
                  ) : (
                    <span>{e.content}</span>
                  )}
                </div>
              ))
            )}
          </div>
        </Card>

        {missingFields.length > 0 ? (
          <Card
            title="缺失参数补全"
            subtitle="AI 解析结果不完整，请补全以下字段后继续自动推进"
            actions={<AlertTriangle className="h-5 w-5 text-amber-500" aria-hidden />}
          >
            <div className="flex flex-col gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <input ref={xlsxInputRef} type="file" accept=".xlsx,.xlsm" className="hidden" onChange={handleExcelImport} />
                <button
                  type="button"
                  onClick={() => xlsxInputRef.current?.click()}
                  className="inline-flex items-center gap-2 rounded-lg border border-amber-300/60 bg-amber-50 px-3 py-1.5 text-xs font-medium text-amber-900 hover:bg-amber-100 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-100 dark:hover:bg-amber-900/50"
                >
                  <FileSpreadsheet className="h-3.5 w-3.5" />
                  从 Excel 批量回填
                </button>
                <span className="text-xs text-slate-500">
                  前两列：字段路径、取值；首行可为表头（含「字段」「field」等关键字则跳过）
                </span>
              </div>
              {missingFields.map((m) => (
                <label key={m.id || m.field_path} className="text-sm font-medium text-slate-700 dark:text-slate-200">
                  <span className="flex items-center justify-between gap-2">
                    <span>{m.field_path}</span>
                    <span className="text-xs font-normal text-slate-500">{m.reason}</span>
                  </span>
                  <input
                    className={INPUT + " mt-1"}
                    value={supplementValues[m.field_path] ?? ""}
                    onChange={(e) =>
                      setSupplementValues({
                        ...supplementValues,
                        [m.field_path]: e.target.value,
                      })
                    }
                    placeholder={`请输入 ${m.field_path}`}
                  />
                </label>
              ))}
              <button
                type="button"
                onClick={submitSupplement}
                disabled={supplementSubmitting}
                className="self-start rounded-lg bg-amber-500 px-4 py-2 text-sm font-medium text-white hover:bg-amber-600 disabled:opacity-60"
              >
                {supplementSubmitting ? "提交中…" : "提交补全并继续"}
              </button>
            </div>
          </Card>
        ) : null}

        <Card title="BDI 执行回执" subtitle="下游执行的核心 ID 与日志">
          {(task?.bdi_bindings || []).length === 0 ? (
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {task ? "尚未进入 BDI 执行阶段" : "尚未发起任务"}
            </p>
          ) : (
            <div className="flex flex-col gap-3">
              {(task.bdi_bindings || []).map((b) => (
                <div
                  key={b.id}
                  className="rounded-lg border border-slate-100 p-3 text-sm dark:border-slate-800"
                >
                  <div className="flex flex-wrap items-center gap-3">
                    <Badge status={b.full_status === "succeeded" ? "completed" : b.full_status} />
                    <span className="text-slate-500 dark:text-slate-400">最后阶段: {b.last_step || "-"}</span>
                  </div>
                  <dl className="mt-2 grid grid-cols-1 gap-x-4 gap-y-1 text-xs md:grid-cols-2">
                    <div>
                      <dt className="inline text-slate-500">bdi_task_id：</dt>
                      <dd className="inline font-mono">{b.bdi_task_id || "-"}</dd>
                    </div>
                    <div>
                      <dt className="inline text-slate-500">flow：</dt>
                      <dd className="inline font-mono">{b.bdi_flow_id || "-"}</dd>
                    </div>
                    <div>
                      <dt className="inline text-slate-500">model：</dt>
                      <dd className="inline font-mono">{b.bdi_model_id || "-"}</dd>
                    </div>
                    <div>
                      <dt className="inline text-slate-500">mapping：</dt>
                      <dd className="inline font-mono">{b.bdi_mapping_id || "-"}</dd>
                    </div>
                  </dl>
                  {(b.execute_log || []).length > 0 ? (
                    <pre className="mt-2 max-h-32 overflow-auto whitespace-pre-wrap rounded bg-slate-50 px-2 py-1 text-[12px] text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                      {JSON.stringify(b.execute_log, null, 2)}
                    </pre>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </Card>

        {task?.config_snapshot?.bdi_payload ? (
          <Card title="BDI 入参预览" subtitle="已归一化为 16 字段标准入参">
            <pre className="max-h-56 overflow-auto whitespace-pre-wrap rounded bg-slate-50 p-3 text-[12px] dark:bg-slate-800 dark:text-slate-200">
              {JSON.stringify(task.config_snapshot.bdi_payload, null, 2)}
            </pre>
          </Card>
        ) : null}

        {finished ? (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700 dark:border-emerald-900/40 dark:bg-emerald-900/20 dark:text-emerald-300">
            {task.status === "completed" ? "🎉 任务已完成" : "❌ 任务失败：" + (task.error_message || "请查看异常日志")}
          </div>
        ) : null}
      </div>
    </div>
  );
}
