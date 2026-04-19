import React, { Suspense, useCallback, useEffect, useState } from "react";
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
  } = useTopologyStream();
  const [selected, setSelected] = useState(null);
  const [perfMode, setPerfMode] = useState(false);

  const handleSelect = useCallback((node) => {
    setSelected(node);
  }, []);

  // 快捷键：R 重置视角 / F 切全屏 / P 暂停
  useEffect(() => {
    const onKey = (e) => {
      if (e.target && ["INPUT", "TEXTAREA"].includes(e.target.tagName)) return;
      if (e.key === "p" || e.key === "P") togglePause();
      if (e.key === "f" || e.key === "F") {
        const el = document.documentElement;
        if (!document.fullscreenElement) el.requestFullscreen?.();
        else document.exitFullscreen?.();
      }
      if (e.key === "b" || e.key === "B") setPerfMode((v) => !v);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [togglePause]);

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

      {/* 左下角快捷键提示 */}
      <div className="pointer-events-none absolute bottom-4 left-4 hidden rounded-lg border border-slate-700/50 bg-slate-900/60 px-3 py-1.5 text-[11px] text-slate-400 backdrop-blur sm:block">
        <span className="mr-2">快捷键：</span>
        <kbd className="rounded bg-slate-800 px-1">P</kbd> 暂停粒子 ·
        <kbd className="ml-1 rounded bg-slate-800 px-1">F</kbd> 全屏 ·
        <kbd className="ml-1 rounded bg-slate-800 px-1">B</kbd> 性能模式
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
