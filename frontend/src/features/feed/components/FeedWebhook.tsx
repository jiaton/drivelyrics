import { useState } from "react";
import { Button } from "../../../components/ui/Button";
import { CopyBox } from "../../../components/ui/CopyBox";
import { TextField } from "../../../components/ui/TextField";
import { useI18n } from "../../../i18n";
import { fill } from "../../../i18n/rich";
import { feedApi } from "../api/feedApi";
import type { FeedSettings } from "../types";

/** The optional webhook: URL, signing secret (shown once), test, removal. */
export function FeedWebhook({ settings, onChanged }: { settings: FeedSettings; onChanged: () => void }) {
  const { t } = useI18n();
  const tf = t.app.feed;
  const [url, setUrl] = useState(settings.webhook_url);
  const [secret, setSecret] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const run = (work: Promise<unknown>) => work.then(onChanged).catch((err: Error) => setNote(err.message));

  return (
    <section className="feed-section">
      <h2>{tf.webhookTitle}</h2>
      <p className="feed-hint">{tf.webhookHint}</p>
      {settings.webhook_paused ? <p className="feed-warning">{tf.webhookPaused}</p> : null}
      <TextField label={tf.webhookUrl} value={url} placeholder="https://" onChange={(e) => setUrl(e.target.value)} />
      <div className="feed-row" style={{ justifyContent: "flex-start" }}>
        <Button
          onClick={() => {
            setNote(null);
            run(feedApi.saveWebhook(url).then((saved) => setSecret(saved.secret ?? null)));
          }}
        >
          {tf.webhookSave}
        </Button>
        {settings.webhook_url ? (
          <>
            <Button
              variant="secondary"
              onClick={() =>
                feedApi
                  .testWebhook()
                  .then((r) => setNote(fill(tf.testResult[r.ok ? "ok" : "failed"], { detail: r.detail })))
                  .catch((err: Error) => setNote(err.message))
              }
            >
              {tf.webhookTest}
            </Button>
            <Button
              variant="ghost"
              onClick={() => {
                if (window.confirm(tf.webhookRotateConfirm)) run(feedApi.rotateSecret().then((r) => setSecret(r.secret)));
              }}
            >
              {tf.webhookRotate}
            </Button>
            <Button
              variant="ghost"
              onClick={() => {
                setSecret(null);
                setUrl("");
                run(feedApi.removeWebhook());
              }}
            >
              {tf.webhookRemove}
            </Button>
          </>
        ) : null}
      </div>
      {secret ? (
        <div className="feed-reveal">
          <span>{tf.webhookSecret}</span>
          <CopyBox value={secret} />
        </div>
      ) : null}
      {note ? <p className="feed-hint">{note}</p> : null}
    </section>
  );
}
