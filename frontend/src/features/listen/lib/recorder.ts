/**
 * The microphone, opened once per listen session (so auto-listening for the next song
 * doesn't ask for permission again) and recorded in short clips. Browser audio
 * processing is turned off: echo cancellation and noise suppression are tuned for
 * speech and eat the music a fingerprint needs.
 */
export class MicRecorder {
  private stream: MediaStream | null = null;

  static supported(): boolean {
    return typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== "undefined";
  }

  async open(): Promise<void> {
    if (this.stream) return;
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
    });
  }

  /** Records `ms` of sound. `startedAt` is performance.now() when recording began. */
  record(ms: number): Promise<{ blob: Blob; startedAt: number; filename: string }> {
    const stream = this.stream;
    if (!stream) return Promise.reject(new Error("microphone not open"));
    const mimeType = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"].find((t) => MediaRecorder.isTypeSupported(t));
    const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    const chunks: Blob[] = [];
    return new Promise((resolve, reject) => {
      let startedAt = 0;
      recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
      recorder.onstart = () => {
        startedAt = performance.now();
        window.setTimeout(() => recorder.state === "recording" && recorder.stop(), ms);
      };
      recorder.onerror = () => reject(new Error("recording failed"));
      recorder.onstop = () => {
        const type = recorder.mimeType || mimeType || "audio/webm";
        const ext = type.includes("mp4") ? "m4a" : type.includes("ogg") ? "ogg" : "webm";
        resolve({ blob: new Blob(chunks, { type }), startedAt, filename: `clip.${ext}` });
      };
      recorder.start();
    });
  }

  close(): void {
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
  }
}
