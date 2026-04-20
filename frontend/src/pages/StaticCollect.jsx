import { Navigate } from "react-router-dom";

/** @deprecated 请使用 /offline-collect/province */
export default function StaticCollect() {
  return <Navigate to="/offline-collect/province" replace />;
}
