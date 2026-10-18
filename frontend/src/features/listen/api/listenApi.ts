import { api } from "../../../lib/api";
import type { Schema } from "../../../lib/schema";

export type Recognized = Schema<"RecognizeResponse">;
export type KeyStatus = Schema<"RecognizerKeyStatus">;

export const listenApi = {
  keyStatus: () => api<KeyStatus>("/api/recognize/key"),
  saveKey: (token: string) => api<KeyStatus>("/api/recognize/key", { method: "PUT", json: { token } }),
  removeKey: () => api("/api/recognize/key", { method: "DELETE" }),
  recognize: (blob: Blob, filename: string, clipMs: number) => {
    const form = new FormData();
    form.append("audio", blob, filename);
    form.append("clip_ms", String(Math.round(clipMs)));
    return api<Recognized>("/api/recognize", { method: "POST", body: form });
  },
};
