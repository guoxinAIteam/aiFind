import React, { useMemo } from "react";
import { OrbitControls, Stars, Grid, Html } from "@react-three/drei";
import { EffectComposer, Bloom } from "@react-three/postprocessing";
import Nodes from "./Nodes";
import Edges from "./Edges";
import ActiveFlows from "./ActiveFlows";
import { computeNodePositions, LAYER_NAMES, LAYER_Z } from "./layout";

export default function Scene({
  snapshot,
  activeTasks,
  selectedKey,
  onSelectNode,
  enableBloom = true,
  paused = false,
}) {
  const nodes = snapshot?.nodes || [];
  const edges = snapshot?.edges || [];
  const positions = useMemo(() => computeNodePositions(nodes), [nodes]);

  return (
    <>
      <color attach="background" args={["#030712"]} />
      <fog attach="fog" args={["#030712", 30, 90]} />

      <ambientLight intensity={0.25} />
      <directionalLight position={[10, 20, 10]} intensity={0.8} color="#a5b4fc" />
      <pointLight position={[-20, 10, -20]} intensity={0.6} color="#22d3ee" />
      <pointLight position={[20, 10, 20]} intensity={0.6} color="#f472b6" />

      <Stars radius={120} depth={60} count={1200} factor={3} fade speed={0.4} />

      {/* 地面网格 */}
      <Grid
        position={[0, -4.5, 0]}
        args={[120, 120]}
        cellSize={1}
        cellThickness={0.5}
        cellColor="#1e293b"
        sectionSize={10}
        sectionThickness={1.2}
        sectionColor="#334155"
        fadeDistance={80}
        fadeStrength={1}
        followCamera={false}
        infiniteGrid
      />

      {/* 层标签 */}
      {Object.entries(LAYER_NAMES).map(([layer, label]) => (
        <Html
          key={layer}
          position={[-24, 6, LAYER_Z[layer]]}
          transform={false}
          zIndexRange={[0, 0]}
          occlude={false}
        >
          <div
            className="select-none rounded-md border border-slate-600/50 bg-slate-900/70 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.25em] text-slate-200 backdrop-blur-sm"
            style={{ pointerEvents: "none" }}
          >
            Layer {layer} · {label}
          </div>
        </Html>
      ))}

      <Edges edges={edges} nodes={nodes} positions={positions} />
      <Nodes
        nodes={nodes}
        positions={positions}
        onSelect={onSelectNode}
        selectedKey={selectedKey}
      />
      <ActiveFlows
        tasks={activeTasks}
        positions={positions}
        nodes={nodes}
        paused={paused}
      />

      <OrbitControls
        makeDefault
        enablePan
        minDistance={15}
        maxDistance={80}
        maxPolarAngle={Math.PI / 2.1}
      />

      {enableBloom ? (
        <EffectComposer disableNormalPass>
          <Bloom
            mipmapBlur
            luminanceThreshold={0.25}
            luminanceSmoothing={0.1}
            intensity={0.85}
          />
        </EffectComposer>
      ) : null}
    </>
  );
}
