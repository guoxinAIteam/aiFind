import React, { useMemo } from "react";
import { Line } from "@react-three/drei";
import { LAYER_COLORS } from "./layout";

// 将节点连线渲染为 drei <Line>，颜色取"源节点所在层颜色"渐变到目标节点所在层颜色
export default function Edges({ edges, nodes, positions }) {
  const nodeByKey = useMemo(() => {
    const m = new Map();
    for (const n of nodes || []) m.set(n.key, n);
    return m;
  }, [nodes]);

  const entries = useMemo(() => {
    const out = [];
    for (const e of edges || []) {
      const a = positions.get(e.from);
      const b = positions.get(e.to);
      if (!a || !b) continue;
      const na = nodeByKey.get(e.from);
      const nb = nodeByKey.get(e.to);
      if (!na || !nb) continue;
      const ca = LAYER_COLORS[na.layer] || "#64748b";
      const cb = LAYER_COLORS[nb.layer] || "#64748b";
      // 在连线中点略微上抬，形成弧度，避免直线交叠过度
      const mid = [
        (a[0] + b[0]) / 2,
        Math.max(a[1], b[1]) + 2.8,
        (a[2] + b[2]) / 2,
      ];
      out.push({ key: `${e.from}->${e.to}`, points: [a, mid, b], vertexColors: [ca, ca, cb] });
    }
    return out;
  }, [edges, positions, nodeByKey]);

  return (
    <group>
      {entries.map((e) => (
        <Line
          key={e.key}
          points={e.points}
          vertexColors={e.vertexColors}
          lineWidth={1.2}
          transparent
          opacity={0.7}
          dashed={false}
        />
      ))}
    </group>
  );
}
