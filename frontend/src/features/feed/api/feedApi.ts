import { api } from "../../../lib/api";
import type { DeliveryResult, FeedSettings, FeedSettingsPatch, FeedStatus, FeedTokenCreated, FeedTokenInfo, WebhookSaved } from "../types";

export const feedApi = {
  status: () => api<FeedStatus>("/api/feed/status"),
  tokens: () => api<{ tokens: FeedTokenInfo[] }>("/api/feed/tokens").then((b) => b.tokens),
  createToken: (name: string) => api<FeedTokenCreated>("/api/feed/tokens", { method: "POST", json: { name } }),
  revokeToken: (id: number) => api(`/api/feed/tokens/${id}`, { method: "DELETE" }),
  settings: () => api<FeedSettings>("/api/feed/settings"),
  saveSettings: (patch: FeedSettingsPatch) => api<FeedSettings>("/api/feed/settings", { method: "PUT", json: patch }),
  saveWebhook: (url: string) => api<WebhookSaved>("/api/feed/webhook", { method: "PUT", json: { url } }),
  removeWebhook: () => api("/api/feed/webhook", { method: "DELETE" }),
  rotateSecret: () => api<{ secret: string }>("/api/feed/webhook/secret", { method: "POST" }),
  testWebhook: () => api<DeliveryResult>("/api/feed/webhook/test", { method: "POST" }),
  refresh: (confirmOverBudget = false) => api("/api/feed/refresh", { method: "POST", json: { confirm_over_budget: confirmOverBudget } }),
};
