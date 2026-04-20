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
    createStatic: (data) =>
      request("/flows/static", { method: "POST", body: JSON.stringify(data) }),
    getStatic: (id) => request(`/flows/${id}/static`),
    supplement: (id, values) =>
      request(`/flows/${id}/supplement`, {
        method: "POST",
        body: JSON.stringify({ values }),
      }),
    supplementImportExcel: async (id, file) => {
      const fd = new FormData();
      fd.append("file", file);
      return request(`/flows/${id}/supplement/import-excel`, { method: "POST", body: fd });
    },
    listStatic: (params = {}) => {
      const sp = new URLSearchParams();
      if (params.q != null && String(params.q).trim()) sp.set("q", String(params.q).trim());
      if (params.status != null && String(params.status).trim())
        sp.set("status", String(params.status).trim());
      if (params.category != null && String(params.category).trim())
        sp.set("category", String(params.category).trim());
      if (params.page != null) sp.set("page", String(params.page));
      if (params.page_size != null) sp.set("page_size", String(params.page_size));
      const qs = sp.toString();
      return request(`/flows/static/list${qs ? `?${qs}` : ""}`);
    },
  },
  parse: {
    requirement: (data) =>
      request("/parse/requirement", { method: "POST", body: JSON.stringify(data) }),
    get: (id) => request(`/parse/${id}`),
    supplement: (id, values) =>
      request(`/parse/${id}/supplement`, {
        method: "POST",
        body: JSON.stringify({ values }),
      }),
    // SSE 流式解析（返回原始 Response 供调用方读取 ReadableStream）
    stream: (data) =>
      fetch("/api/parse/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify(data),
      }),
    extractDocx: async (file) => {
      const fd = new FormData();
      fd.append("file", file);
      return request("/parse/docx", { method: "POST", body: fd });
    },
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
  topology: {
    snapshot: () => request("/topology/snapshot"),
    nodeDetail: (nodeKey) => request(`/topology/nodes/${nodeKey}`),
    // 返回一个 EventSource，交给调用方负责 onmessage/onerror
    stream: () => new EventSource("/api/topology/stream"),
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
