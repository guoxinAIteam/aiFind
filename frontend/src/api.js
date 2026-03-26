const BASE = "/api";

async function request(path, opts = {}) {
  const headers =
    opts.body instanceof FormData
      ? { ...opts.headers }
      : { "Content-Type": "application/json", ...opts.headers };

  const res = await fetch(`${BASE}${path}`, {
    headers,
    ...opts,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const api = {
  dashboard: () => request("/dashboard"),
  flows: {
    list: (params = {}) => {
      const sp = new URLSearchParams();
      if (params.page != null) sp.set("page", String(params.page));
      if (params.page_size != null) sp.set("page_size", String(params.page_size));
      const qs = sp.toString();
      return request(`/flows${qs ? `?${qs}` : ""}`);
    },
    get: (id) => request(`/flows/${id}`),
    create: (data) => request("/flows", { method: "POST", body: JSON.stringify(data) }),
    execute: (id) => request(`/flows/${id}/execute`, { method: "POST" }),
    confirmOperation: (taskId, stepOrder, body) =>
      request(`/flows/${taskId}/step/${stepOrder}/confirm`, {
        method: "POST",
        body: JSON.stringify(body ?? {}),
      }),
    completeStep: (taskId, step) =>
      request(`/flows/${taskId}/step/${step}/complete`, { method: "POST" }),
  },
  doc: {
    parse: async (file) => {
      const fd = new FormData();
      fd.append("file", file);
      return request("/doc/parse", { method: "POST", body: fd });
    },
  },
  params: {
    list: (params = {}) => {
      const sp = new URLSearchParams();
      if (params.page != null) sp.set("page", String(params.page));
      if (params.page_size != null) sp.set("page_size", String(params.page_size));
      const qs = sp.toString();
      return request(`/params${qs ? `?${qs}` : ""}`);
    },
    get: (id) => request(`/params/${id}`),
    create: (data) => request("/params", { method: "POST", body: JSON.stringify(data) }),
    validate: (params) => request("/params/validate", { method: "POST", body: JSON.stringify({ params }) }),
    recommend: (table_name) =>
      request("/params/recommend", { method: "POST", body: JSON.stringify({ table_name }) }),
  },
  monitor: {
    events: (params = {}) => {
      const sp = new URLSearchParams();
      if (typeof params === "string") {
        if (params) sp.set("severity", params);
      } else if (params && typeof params === "object") {
        if (params.severity) sp.set("severity", params.severity);
        if (params.page != null) sp.set("page", String(params.page));
        if (params.page_size != null) sp.set("page_size", String(params.page_size));
      }
      const qs = sp.toString();
      return request(`/monitor/events${qs ? `?${qs}` : ""}`);
    },
    metrics: (source) => request(`/monitor/metrics${source ? `?source=${source}` : ""}`),
    resolve: (id) => request(`/monitor/events/${id}/resolve`, { method: "POST" }),
    detectAnomaly: (metrics) =>
      request("/monitor/anomaly-detect", { method: "POST", body: JSON.stringify({ metrics }) }),
  },
  knowledge: {
    list: (params = {}) => {
      const sp = new URLSearchParams();
      if (typeof params === "string") {
        if (params.trim()) sp.set("q", params.trim());
      } else if (params && typeof params === "object") {
        if (params.q?.trim()) sp.set("q", params.q.trim());
        if (params.category) sp.set("category", params.category);
        if (params.page != null) sp.set("page", String(params.page));
        if (params.page_size != null) sp.set("page_size", String(params.page_size));
      }
      const qs = sp.toString();
      return request(`/knowledge${qs ? `?${qs}` : ""}`);
    },
    get: (id) => request(`/knowledge/${id}`),
    create: (data) => request("/knowledge", { method: "POST", body: JSON.stringify(data) }),
    helpful: (id) => request(`/knowledge/${id}/helpful`, { method: "POST" }),
  },
};
