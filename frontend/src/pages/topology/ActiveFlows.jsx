import React, { useMemo, useRef } from "react";
import * as THREE from "three";
import { useFrame } from "@react-three/fiber";

const SCENARIO_COLORS = {
  static_bdi: new THREE.Color("#34d399"),
  legacy: new THREE.Color("#60a5fa"),
};
const WAITING_COLOR = new THREE.Color("#fbbf24");
const FAILED_COLOR = new THREE.Color("#f43f5e");

// 为任务路径生成一条 CatmullRom 曲线，并在其上撒一组粒子
function buildCurve(path, positions) {
  const pts = [];
  for (const key of path || []) {
    const p = positions.get(key);
    if (p) pts.push(new THREE.Vector3(p[0], p[1] + 1.2, p[2]));
  }
  if (pts.length < 2) return null;
  return new THREE.CatmullRomCurve3(pts, false, "catmullrom", 0.5);
}

function FlowLine({ task, curve, paused }) {
  const particlesRef = useRef();
  const tubeRef = useRef();
  const progressRef = useRef(task.progress || 0);

  // 平滑追踪后端传来的 progress
  useFrame((_, dt) => {
    if (paused) return;
    const target = task.progress || 0;
    const cur = progressRef.current;
    progressRef.current = cur + (target - cur) * Math.min(1, dt * 1.5);

    if (particlesRef.current) {
      const geom = particlesRef.current.geometry;
      const pos = geom.attributes.position;
      const count = pos.count;
      const baseT = progressRef.current / 100;
      const now = performance.now() / 1000;
      for (let i = 0; i < count; i++) {
        // 沿曲线分布：锚定在当前 progress，再在其前后散布 0~0.15
        const spread = (i / count) * 0.18;
        let t = baseT - spread + 0.02 * Math.sin(now * 2 + i);
        t = ((t % 1) + 1) % 1;
        const p = curve.getPoint(t);
        pos.setXYZ(i, p.x, p.y, p.z);
      }
      pos.needsUpdate = true;

      // 颜色：默认按场景配色；等待/失败覆盖
      let color = SCENARIO_COLORS[task.scenario] || SCENARIO_COLORS.legacy;
      if (task.status === "waiting_supplement") color = WAITING_COLOR;
      if (task.status === "failed") color = FAILED_COLOR;
      particlesRef.current.material.color.copy(color);
      particlesRef.current.material.size = task.status === "failed" ? 0.55 : 0.35;
    }
    if (tubeRef.current) {
      const mat = tubeRef.current.material;
      const failed = task.status === "failed";
      const waiting = task.status === "waiting_supplement";
      mat.opacity = waiting ? 0.22 : 0.15;
      mat.color.copy(failed ? FAILED_COLOR : waiting ? WAITING_COLOR : (SCENARIO_COLORS[task.scenario] || SCENARIO_COLORS.legacy));
    }
  });

  // 粒子几何体：30 个点，位置每帧更新
  const geom = useMemo(() => {
    const g = new THREE.BufferGeometry();
    const n = 30;
    const arr = new Float32Array(n * 3);
    g.setAttribute("position", new THREE.BufferAttribute(arr, 3));
    return g;
  }, []);

  const tubeGeom = useMemo(() => {
    try {
      return new THREE.TubeGeometry(curve, 48, 0.08, 8, false);
    } catch (_) {
      return null;
    }
  }, [curve]);

  return (
    <group>
      {tubeGeom ? (
        <mesh ref={tubeRef} geometry={tubeGeom}>
          <meshBasicMaterial
            color={SCENARIO_COLORS[task.scenario] || SCENARIO_COLORS.legacy}
            transparent
            opacity={0.15}
            toneMapped={false}
          />
        </mesh>
      ) : null}
      <points ref={particlesRef} geometry={geom}>
        <pointsMaterial
          size={0.35}
          color={SCENARIO_COLORS[task.scenario] || SCENARIO_COLORS.legacy}
          transparent
          opacity={0.95}
          sizeAttenuation
          depthWrite={false}
          toneMapped={false}
          blending={THREE.AdditiveBlending}
        />
      </points>
    </group>
  );
}

const FlowLineMemo = React.memo(FlowLine);

export default function ActiveFlows({ tasks, positions, paused, maxLines = 50 }) {
  const enriched = useMemo(() => {
    const arr = [];
    for (const t of tasks || []) {
      const curve = buildCurve(t.path, positions);
      if (!curve) continue;
      arr.push({ task: t, curve });
      if (arr.length >= maxLines) break;
    }
    return arr;
  }, [tasks, positions, maxLines]);

  return (
    <group>
      {enriched.map(({ task, curve }) => (
        <FlowLineMemo key={task.id} task={task} curve={curve} paused={paused} />
      ))}
    </group>
  );
}
