import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  GitBranch,
  Settings,
  Activity,
  BookOpen,
  Library,
  Zap,
  RadioTower,
  ChevronDown,
  ChevronRight,
  Sun,
  Moon,
  Monitor,
} from "lucide-react";
import { useEffect, useState } from "react";
import Copilot from "./Copilot";
import { getTheme, setTheme } from "../theme";

const navItems = [
  { to: "/", end: true, label: "工作台", Icon: LayoutDashboard },
  // 「采集场景管理」目录分组：订单采集 / 离线采集 / 省分个采
  { to: "/params", label: "参数管理", Icon: Settings },
  { to: "/monitor", label: "监控中心", Icon: Activity },
  { to: "/topology", label: "全景大屏 3D", Icon: RadioTower },
  { to: "/knowledge", label: "知识库", Icon: BookOpen },
  { to: "/manual", label: "操作手册", Icon: Library },
];

const PAGE_TITLES = {
  "/": "工作台",
  "/flows": "订单采集管理",
  "/offline-collect": "离线采集",
  "/offline-collect/province": "省分个采",
  "/static-collect": "静态采集（重定向）",
  "/params": "参数管理",
  "/monitor": "监控中心",
  "/topology": "全景大屏 3D",
  "/knowledge": "知识库",
  "/manual": "操作手册",
};

export default function Layout() {
  const { pathname } = useLocation();
  const pageTitle =
    pathname.startsWith("/offline-collect/province")
      ? "省分个采"
      : pathname.startsWith("/offline-collect")
        ? "离线采集"
        : PAGE_TITLES[pathname] ?? "智能采集运营平台";
  const [theme, setThemeState] = useState(() => getTheme());
  const [flowsOpen, setFlowsOpen] = useState(
    () =>
      pathname.startsWith("/flows") ||
      pathname.startsWith("/offline-collect") ||
      pathname.startsWith("/static-collect"),
  );

  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      if (getTheme() === "system") {
        setThemeState("system");
      }
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  useEffect(() => {
    if (
      pathname.startsWith("/flows") ||
      pathname.startsWith("/offline-collect") ||
      pathname.startsWith("/static-collect")
    )
      setFlowsOpen(true);
  }, [pathname]);

  const cycleTheme = () => {
    const next = theme === "light" ? "dark" : theme === "dark" ? "system" : "light";
    setTheme(next);
    setThemeState(next);
  };

  const ThemeIcon = theme === "light" ? Sun : theme === "dark" ? Moon : Monitor;
  const themeLabel = theme === "light" ? "浅色" : theme === "dark" ? "深色" : "跟随系统";

  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <aside className="flex w-60 shrink-0 flex-col bg-slate-900 text-white">
        <div className="flex items-center gap-2 border-b border-slate-800 px-4 py-5">
          <Zap className="h-8 w-8 shrink-0 text-indigo-400" aria-hidden />
          <span className="text-sm font-semibold leading-tight">
            智能采集运营平台
          </span>
        </div>
        <nav className="flex flex-1 flex-col gap-1 p-3">
          <div className="mb-1">
            <button
              type="button"
              onClick={() => setFlowsOpen((v) => !v)}
              className="flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-left text-sm font-medium text-slate-300 transition-colors hover:bg-slate-800 hover:text-white"
              aria-expanded={flowsOpen}
            >
              <span className="flex items-center gap-3">
                <GitBranch className="h-5 w-5 shrink-0" aria-hidden />
                采集场景管理
              </span>
              {flowsOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            </button>
            {flowsOpen ? (
              <div className="mt-1 flex flex-col gap-1 pl-2">
                <NavLink
                  to="/flows"
                  className={({ isActive }) =>
                    [
                      "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                      isActive
                        ? "bg-indigo-600 text-white shadow-sm"
                        : "text-slate-300 hover:bg-slate-800 hover:text-white",
                    ].join(" ")
                  }
                >
                  <span className="h-2 w-2 rounded-full bg-indigo-300/70" aria-hidden />
                  订单采集管理
                </NavLink>
                <NavLink
                  to="/offline-collect"
                  end
                  className={({ isActive }) =>
                    [
                      "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                      isActive
                        ? "bg-indigo-600 text-white shadow-sm"
                        : "text-slate-300 hover:bg-slate-800 hover:text-white",
                    ].join(" ")
                  }
                >
                  <span className="h-2 w-2 rounded-full bg-emerald-300/70" aria-hidden />
                  离线采集
                </NavLink>
                <NavLink
                  to="/offline-collect/province"
                  className={({ isActive }) =>
                    [
                      "ml-4 flex items-center gap-3 rounded-lg border-l-2 border-slate-600 py-1.5 pl-3 pr-2 text-xs font-medium transition-colors",
                      isActive
                        ? "border-indigo-400 bg-indigo-600/90 text-white shadow-sm"
                        : "border-transparent text-slate-400 hover:bg-slate-800 hover:text-white",
                    ].join(" ")
                  }
                >
                  <span className="h-1.5 w-1.5 rounded-full bg-teal-300/80" aria-hidden />
                  省分个采
                </NavLink>
              </div>
            ) : null}
          </div>
          {navItems.map(({ to, end, label, Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                [
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "text-slate-300 hover:bg-slate-800 hover:text-white",
                ].join(" ")
              }
            >
              <Icon className="h-5 w-5 shrink-0" aria-hidden />
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <header className="shrink-0 border-b border-slate-200 bg-white px-6 py-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-center justify-between gap-3">
            <h1 className="text-lg font-semibold tracking-tight text-slate-900 dark:text-slate-100">
              {pageTitle}
            </h1>
            <button
              type="button"
              onClick={cycleTheme}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
              title={`当前主题：${themeLabel}（点击切换）`}
            >
              <ThemeIcon className="h-4 w-4" />
              <span>{themeLabel}</span>
            </button>
          </div>
        </header>
        <main className="min-h-0 flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
      <Copilot />
    </div>
  );
}
