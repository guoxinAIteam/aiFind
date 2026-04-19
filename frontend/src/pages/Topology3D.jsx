import React, { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { Canvas } from "@react-three/fiber";
import Scene from "./topology/Scene";
import Hud from "./topology/Hud";
import DetailPanel from "./topology/DetailPanel";
import { useTopologyStream } from "./topology/useTopologyStream";

export default function Topology3D() {
  const {
    snapshot,
    stats,
    activeTasks,
    events,
    connState,
    paused,
    togglePause,
    highlightMap,
  } = useTopologyStream();
  const [selected, setSelected] = useState(null);
  const [perfModeManual, setPerfModeManual] = useState(null); // null 表示跟随自动
  const controlsRef = useRef();

  // 自动 LOD：活跃任务 > 50 时自动开启性能模式（关闭 Bloom），但用户手动切换后以用户为准
  const autoPerfMode = (activeTasks?.length || 0) > 50;
  const perfMode = perfModeManual == null ? autoPerfMode : perfModeManual;

  const handleSelect = useCallback((node) => {
    setSelected(node);
  }, []);

  // 快捷键：R 重置视角 / F 切全屏 / P 暂停 / B 性能模式
  useEffect(() => {
    const onKey = (e) => {
      if (e.target && ["INPUT", "TEXTAREA"].includes(e.target.tagName)) return;
      const k = e.key.toLowerCase();
      if (k === "p") togglePause();
      else if (k === "f") {
        const el = document.documentElement;
        if (!document.fullscreenElement) el.requestFullscreen?.();
        else document.exitFullscreen?.();
      } else if (k === "b") setPerfModeManual((v) => !(v == null ? autoPerfMode : v));
      else if (k === "r") controlsRef.current?.reset?.();
      else if (k === "escape") setSelected(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [togglePause, autoPerfMode]);

  return (
    <div className="relative h-[calc(100vh-120px)] w-full overflow-hidden rounded-2xl border border-slate-800 bg-slate-950 shadow-2xl">
      <Canvas
        dpr={[1, 1.75]}
        camera={{ position: [24, 14, 32], fov: 55 }}
        gl={{ antialias: true, alpha: false, powerPreference: "high-performance" }}
      >
        <Suspense fallback={null}>
          <Scene
            snapshot={snapshot}
            activeTasks={activeTasks}
            selectedKey={selected?.key}
            onSelectNode={handleSelect}
            enableBloom={!perfMode}
            paused={paused}
            highlightMap={highlightMap}
            controlsRef={controlsRef}
          />
        </Suspense>
      </Canvas>

      <Hud
        stats={stats}
        connState={connState}
        paused={paused}
        onTogglePause={togglePause}
        events={events}
      />

      <DetailPanel node={selected} onClose={() => setSelected(null)} />

      {/* 左下角快捷键提示 + 模式徽章 */}
      <div className="pointer-events-none absolute bottom-4 left-4 hidden rounded-lg border border-slate-700/50 bg-slate-900/60 px-3 py-1.5 text-[11px] text-slate-300 backdrop-blur sm:flex sm:items-center sm:gap-2">
        <span className="text-slate-400">快捷键</span>
        <kbd className="rounded bg-slate-800 px-1">R</kbd>
        <span className="text-slate-500">重置视角</span>
        <kbd className="rounded bg-slate-800 px-1">P</kbd>
        <span className="text-slate-500">暂停粒子</span>
        <kbd className="rounded bg-slate-800 px-1">F</kbd>
        <span className="text-slate-500">全屏</span>
        <kbd className="rounded bg-slate-800 px-1">B</kbd>
        <span className="text-slate-500">性能模式</span>
        {perfMode ? (
          <span className="ml-2 rounded bg-amber-500/20 px-1.5 py-0.5 text-[10px] text-amber-200">
            性能模式已启用{perfModeManual == null ? "（自动）" : ""}
          </span>
        ) : null}
      </div>

      {/* 左上角（返回 HUD 下方）：提示未加载 */}
      {!snapshot ? (
        <div className="absolute inset-0 flex items-center justify-center bg-slate-950/40 text-sm text-slate-300 backdrop-blur-sm">
          正在装配 3D 拓扑…
        </div>
      ) : null}
    </div>
  );
}
