import { ChevronLeft, ChevronRight } from "lucide-react";

export default function Pagination({ page, totalPages, total, pageSize, onPageChange }) {
  if (totalPages <= 1) return null;

  const startItem = (page - 1) * pageSize + 1;
  const endItem = Math.min(page * pageSize, total);

  const pages = [];
  const maxVisible = 5;
  let start = Math.max(1, page - Math.floor(maxVisible / 2));
  let end = Math.min(totalPages, start + maxVisible - 1);
  if (end - start + 1 < maxVisible) start = Math.max(1, end - maxVisible + 1);
  for (let i = start; i <= end; i++) pages.push(i);

  const btnBase = "inline-flex items-center justify-center rounded-lg px-3 py-2 text-sm font-medium transition-colors";
  const btnActive = "bg-indigo-600 text-white shadow-sm";
  const btnInactive = "text-slate-700 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800";
  const btnDisabled = "text-slate-300 cursor-not-allowed dark:text-slate-600";

  return (
    <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-between">
      <p className="text-sm text-slate-500 dark:text-slate-400">
        显示 <span className="font-medium text-slate-700 dark:text-slate-200">{startItem}-{endItem}</span> 条，共{" "}
        <span className="font-medium text-slate-700 dark:text-slate-200">{total}</span> 条
      </p>
      <nav className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          className={`${btnBase} ${page <= 1 ? btnDisabled : btnInactive}`}
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        {start > 1 && (
          <>
            <button type="button" onClick={() => onPageChange(1)} className={`${btnBase} ${btnInactive}`}>1</button>
            {start > 2 && <span className="px-1 text-slate-400">…</span>}
          </>
        )}
        {pages.map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => onPageChange(p)}
            className={`${btnBase} ${p === page ? btnActive : btnInactive}`}
          >
            {p}
          </button>
        ))}
        {end < totalPages && (
          <>
            {end < totalPages - 1 && <span className="px-1 text-slate-400">…</span>}
            <button type="button" onClick={() => onPageChange(totalPages)} className={`${btnBase} ${btnInactive}`}>{totalPages}</button>
          </>
        )}
        <button
          type="button"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          className={`${btnBase} ${page >= totalPages ? btnDisabled : btnInactive}`}
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </nav>
    </div>
  );
}
