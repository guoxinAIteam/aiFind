// 3D 拓扑层间坐标布局：5 层沿 -Z 到 +Z 均匀分布，层内沿 X 轴展开、Y 轴上下错位。
// 坐标系：右手系，相机默认视角在 (18, 14, 22)。

export const LAYER_Z = {
  1: -24, // sources
  2: -12, // upstream
  3: 0, // core
  4: 12, // bdi
  5: 24, // targets
};

export const LAYER_NAMES = {
  1: "数据源",
  2: "上游 AI 解析",
  3: "aiFind 决策中枢",
  4: "BDI 执行",
  5: "目标端",
};

export const LAYER_COLORS = {
  1: "#38bdf8", // sky-400
  2: "#a78bfa", // violet-400
  3: "#34d399", // emerald-400
  4: "#fbbf24", // amber-400
  5: "#f472b6", // pink-400
};

export const STATUS_COLORS = {
  idle: "#64748b",
  healthy: "#34d399",
  busy: "#38bdf8",
  warning: "#fbbf24",
  critical: "#f43f5e",
};

// 根据节点按 layer 分组顺序计算坐标
export function computeNodePositions(nodes) {
  const byLayer = new Map();
  for (const n of nodes) {
    if (!byLayer.has(n.layer)) byLayer.set(n.layer, []);
    byLayer.get(n.layer).push(n);
  }
  const positions = new Map();
  for (const [layer, ns] of byLayer.entries()) {
    const spacing = 7.5;
    const total = ns.length;
    const start = -((total - 1) * spacing) / 2;
    ns.forEach((n, i) => {
      const x = start + i * spacing;
      // 相邻节点 Y 轴轻微错位，避免连线完全重叠
      const y = (i % 2 === 0 ? 0.6 : -0.6) + (layer === 3 ? 0.5 : 0);
      const z = LAYER_Z[layer] ?? 0;
      positions.set(n.key, [x, y, z]);
    });
  }
  return positions;
}
