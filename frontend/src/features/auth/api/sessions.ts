import { api } from "../../../lib/api";
import { clearCache } from "../../../lib/cache";
import type { PairInfo, SessionList } from "../types";

export function listSessions() {
  return api<SessionList>("/api/auth/sessions");
}

export function signOutSession(id: string) {
  return api(`/api/auth/sessions/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export async function signOutEverywhere() {
  await api("/api/auth/logout-everywhere", { method: "POST" });
  clearCache();
  window.location.assign("/");
}

export function pairInfo(code: string) {
  return api<PairInfo>(`/api/auth/pair/info?${new URLSearchParams({ code })}`);
}
