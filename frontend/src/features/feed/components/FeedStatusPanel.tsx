import { fill } from "../../../i18n/rich";
import { useI18n } from "../../../i18n";
import type { FeedStatus } from "../types";
import { ago } from "./ago";

/** What's happening right now, refreshed every few seconds — for debugging one's own side. */
export function FeedStatusPanel({ status }: { status: FeedStatus }) {
  const { t } = useI18n();
  const tf = t.app.feed;
  if (!status.enabled) return <p className="feed-status-line">{tf.noToken}</p>;
  const reason = (r: string) => tf.reasons[r] ?? r;
  const push = status.last_push;
  const what = push ? (push.playing ? [push.title, push.artist].filter(Boolean).join(" — ") : tf.paused) + (push.source ? ` (${push.source})` : "") : "";
  return (
    <>
      <p className="feed-status-line">{status.watching ? tf.watching : tf.notWatching}</p>
      <p className="feed-status-line">
        {fill(tf.receivers, { n: String(status.receivers) })} · {tf.webhook[status.webhook]}
        {status.webhook_detail ? ` (${status.webhook_detail})` : ""}
      </p>
      {status.last_event ? (
        <p className="feed-status-line">
          {fill(tf.lastEvent, { reason: reason(status.last_event.reason), ago: ago(tf, status.last_event.at) })}
          {status.last_event.delivered ? "" : tf.undelivered}
        </p>
      ) : null}
      <p className="feed-status-line">{push ? fill(tf.lastPush, { what, ago: ago(tf, push.at) }) : tf.noPush}</p>
      <p className="feed-hint">
        {fill(tf.usage, {
          used: String(status.month_fetches),
          budget: String(status.monthly_budget),
          hour: String(status.hour_fetches),
          left: String(status.hour_left),
          cap: String(status.hourly_cap),
        })}
      </p>
      {status.not_responding ? <p className="feed-warning">{tf.notResponding}</p> : null}
      {status.blocked ? <p className="feed-warning">{tf.blocked[status.blocked]}</p> : null}
      {status.receiver_limited ? <p className="feed-warning">{tf.receiverLimited[status.receiver_limited]}</p> : null}
    </>
  );
}
