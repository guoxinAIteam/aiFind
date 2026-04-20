import React, { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";

const Dashboard = lazy(() => import("./pages/Dashboard"));
const FlowManager = lazy(() => import("./pages/FlowManager"));
const StaticCollect = lazy(() => import("./pages/StaticCollect"));
const OfflineCollectList = lazy(() => import("./pages/OfflineCollectList"));
const ProvinceCollect = lazy(() => import("./pages/ProvinceCollect"));
const ParamManager = lazy(() => import("./pages/ParamManager"));
const Monitor = lazy(() => import("./pages/Monitor"));
const Knowledge = lazy(() => import("./pages/Knowledge"));
const Manual = lazy(() => import("./pages/Manual"));
const Topology3D = lazy(() => import("./pages/Topology3D"));

function LoadingFallback() {
  return (
    <div className="flex min-h-[240px] items-center justify-center">
      <div
        className="h-9 w-9 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent"
        role="status"
        aria-label="加载中"
      />
    </div>
  );
}

export default function App() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="flows" element={<FlowManager />} />
          <Route path="offline-collect" element={<OfflineCollectList />} />
          <Route path="offline-collect/province" element={<ProvinceCollect />} />
          <Route path="static-collect" element={<StaticCollect />} />
          <Route path="params" element={<ParamManager />} />
          <Route path="monitor" element={<Monitor />} />
          <Route path="topology" element={<Topology3D />} />
          <Route path="knowledge" element={<Knowledge />} />
          <Route path="manual" element={<Manual />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
