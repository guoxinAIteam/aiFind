import React, { useMemo, useRef } from "react";
import * as THREE from "three";
import { Html } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { STATUS_COLORS, LAYER_COLORS } from "./layout";

const BOX_EDGES = new THREE.EdgesGeometry(new THREE.BoxGeometry(3.6, 1.6, 0.6));

function NodeCard({ node, position, onSelect, selected }) {
  const ringRef = useRef();
  const boxRef = useRef();
  const statusColor = STATUS_COLORS[node.status] || STATUS_COLORS.idle;
  const layerColor = LAYER_COLORS[node.layer] || "#94a3b8";
  const active = (node.metrics?.active_tasks || 0) > 0;

  useFrame((state) => {
    const t = state.clock.getElapsedTime();
    if (ringRef.current) {
      const pulse = 0.9 + 0.25 * Math.sin(t * 2 + node.layer);
      ringRef.current.scale.set(pulse, pulse, 1);
      ringRef.current.material.opacity = active ? 0.7 : 0.25;
    }
    if (boxRef.current) {
      const mat = boxRef.current.material;
      if (mat) {
        const base = selected ? 0.9 : active ? 0.55 : 0.2;
        mat.emissiveIntensity = base + 0.2 * Math.sin(t * 3 + node.layer);
      }
    }
  });

  const calls = node.metrics?.calls ?? 0;
  const fail = node.metrics?.fail ?? 0;
  const failRate = calls > 0 ? ((fail / calls) * 100).toFixed(1) : "0.0";
  const activeCnt = node.metrics?.active_tasks ?? 0;

  return (
    <group position={position} onClick={(e) => { e.stopPropagation(); onSelect?.(node); }}>
      {/* 地盘 */}
      <mesh ref={ringRef} rotation={[-Math.PI / 2, 0, 0]} position={[0, -1.2, 0]}>
        <ringGeometry args={[1.4, 2.2, 48]} />
        <meshBasicMaterial color={statusColor} transparent opacity={0.35} />
      </mesh>
      {/* 立体卡片 */}
      <mesh ref={boxRef}>
        <boxGeometry args={[3.6, 1.6, 0.6]} />
        <meshStandardMaterial
          color={"#0f172a"}
          emissive={selected ? layerColor : statusColor}
          emissiveIntensity={0.4}
          metalness={0.6}
          roughness={0.25}
        />
      </mesh>
      {/* 边缘线 */}
      <lineSegments geometry={BOX_EDGES}>
        <lineBasicMaterial color={layerColor} transparent opacity={0.85} />
      </lineSegments>
      {/* HTML 贴图文字 */}
      <Html
        center
        distanceFactor={18}
        position={[0, 0, 0.32]}
        occlude={false}
        zIndexRange={[0, 0]}
      >
        <div
          className="select-none text-center"
          style={{
            width: 180,
            pointerEvents: "none",
          }}
        >
          <div
            className="mx-auto rounded-md px-2 py-1 text-xs font-semibold tracking-wide text-white backdrop-blur"
            style={{
              background: `linear-gradient(135deg, ${layerColor}cc, #0f172acc)`,
              boxShadow: `0 0 12px ${layerColor}99`,
              border: `1px solid ${layerColor}`,
            }}
          >
            {node.label}
          </div>
          <div className="mt-1 flex items-center justify-center gap-2 text-[10px] text-slate-200/90">
            <span
              className="inline-flex h-1.5 w-1.5 rounded-full"
              style={{ background: statusColor, boxShadow: `0 0 6px ${statusColor}` }}
            />
            <span>调用 {calls}</span>
            <span className="text-rose-300/90">失败 {failRate}%</span>
            {activeCnt > 0 ? (
              <span className="rounded bg-emerald-500/20 px-1 text-emerald-200">
                活跃 {activeCnt}
              </span>
            ) : null}
          </div>
        </div>
      </Html>
    </group>
  );
}

// 仅在 positions/nodes/select 变化时 re-render
const NodeCardMemo = React.memo(NodeCard);

export default function Nodes({ nodes, positions, onSelect, selectedKey }) {
  const entries = useMemo(() => {
    const out = [];
    for (const n of nodes || []) {
      const p = positions.get(n.key);
      if (p) out.push({ n, p });
    }
    return out;
  }, [nodes, positions]);
  return (
    <group>
      {entries.map(({ n, p }) => (
        <NodeCardMemo
          key={n.key}
          node={n}
          position={p}
          onSelect={onSelect}
          selected={selectedKey === n.key}
        />
      ))}
    </group>
  );
}
