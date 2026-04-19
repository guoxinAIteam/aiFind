import { useEffect, useRef, useState, useCallback } from "react";
import { api } from "../../api";

// 订阅后端 topology snapshot + SSE stream，自动做"快照刷新 + 增量合并 + 断线重试"。
// 阶段 D 再叠加轮询降级；本阶段先实现核心链路 + 事件缓冲。
export function useTopologyStream() {
  const [snapshot, setSnapshot] = useState(null);
  const [stats, setStats] = useState(null);
  const [activeTasks, setActiveTasks] = useState([]);
  const [events, setEvents] = useState([]); // 滚动事件条
  const [connState, setConnState] = useState("idle"); // idle | connecting | open | fallback | error
  const [paused, setPaused] = useState(false);
  const esRef = useRef(null);
  const pollTimerRef = useRef(null);
  const retryRef = useRef({ count: 0, timer: null });
  const mountedRef = useRef(false);

  const refreshSnapshot = useCallback(async () => {
    try {
      const s = await api.topology.snapshot();
      if (!mountedRef.current) return;
      setSnapshot(s);
      setStats(s.stats);
      setActiveTasks(s.active_tasks || []);
    } catch (e) {
      console.warn("[topology] snapshot failed", e);
    }
  }, []);

  const startPolling = useCallback(() => {
    if (pollTimerRef.current) return;
    setConnState("fallback");
    pollTimerRef.current = setInterval(() => {
      refreshSnapshot();
    }, 5000);
  }, [refreshSnapshot]);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (esRef.current) {
      try { esRef.current.close(); } catch (_) {}
      esRef.current = null;
    }
    setConnState("connecting");
    const es = api.topology.stream();
    esRef.current = es;
    es.onopen = () => {
      retryRef.current.count = 0;
      setConnState("open");
      stopPolling();
    };
    es.onmessage = (ev) => {
      try {
        const payload = JSON.parse(ev.data);
        if (payload.type === "task_tick") {
          setActiveTasks(payload.tasks || []);
          if (payload.stats) setStats(payload.stats);
        } else if (payload.type === "event") {
          setEvents((prev) => [payload, ...prev].slice(0, 50));
        }
      } catch (e) {
        // ignore malformed
      }
    };
    es.onerror = () => {
      setConnState("error");
      try { es.close(); } catch (_) {}
      esRef.current = null;
      const n = ++retryRef.current.count;
      const delay = Math.min(8000, 2000 * Math.pow(2, Math.max(0, n - 1)));
      if (n > 3) {
        startPolling();
        return;
      }
      retryRef.current.timer = setTimeout(() => {
        if (mountedRef.current) connect();
      }, delay);
    };
  }, [startPolling, stopPolling]);

  useEffect(() => {
    mountedRef.current = true;
    refreshSnapshot();
    connect();
    return () => {
      mountedRef.current = false;
      if (esRef.current) {
        try { esRef.current.close(); } catch (_) {}
        esRef.current = null;
      }
      if (retryRef.current.timer) clearTimeout(retryRef.current.timer);
      stopPolling();
    };
  }, [connect, refreshSnapshot, stopPolling]);

  const togglePause = useCallback(() => setPaused((v) => !v), []);

  return {
    snapshot,
    stats,
    activeTasks,
    events,
    connState,
    paused,
    togglePause,
    refreshSnapshot,
  };
}
