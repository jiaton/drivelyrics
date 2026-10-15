import { useState } from "react";
import { Button } from "../../../components/ui/Button";
import { useI18n } from "../../../i18n";
import { fill } from "../../../i18n/rich";
import { feedApi } from "../api/feedApi";
import type { FeedSettings } from "../types";
import { Choices } from "./Choices";

/** When fetches are sent (skip/paused checks, off by default) and the cost limits. */
export function FeedSchedule({ settings, onSaved }: { settings: FeedSettings; onSaved: (next: FeedSettings) => void }) {
  const { t } = useI18n();
  const tf = t.app.feed;
  const [budget, setBudget] = useState(String(settings.monthly_budget));
  const [cap, setCap] = useState(String(settings.hourly_cap));
  const [note, setNote] = useState<string | null>(null);

  const save = (patch: Parameters<typeof feedApi.saveSettings>[0]) =>
    feedApi
      .saveSettings(patch)
      .then((next) => {
        onSaved(next);
        setNote(tf.saved);
      })
      .catch((err: Error) => setNote(err.message));

  const off = `${tf.off} (${tf.recommended})`;
  const every = (n: number) => fill(tf.every, { n: String(n) });
  return (
    <>
      <section className="feed-section">
        <h2>{tf.schedule}</h2>
        <p className="feed-hint">{tf.scheduleHint}</p>
        <Choices
          label={tf.skipCheck}
          value={settings.skip_check_s}
          options={[{ value: 0, label: off }, { value: 60, label: every(60) }, { value: 30, label: every(30) }]}
          onChange={(v) => save({ skip_check_s: v })}
        />
        <Choices
          label={tf.pausedCheck}
          value={settings.paused_check_s}
          options={[{ value: 0, label: off }, { value: 120, label: every(120) }, { value: 60, label: every(60) }]}
          onChange={(v) => save({ paused_check_s: v })}
        />
      </section>
      <section className="feed-section">
        <h2>{tf.limits}</h2>
        <div className="feed-row">
          <label htmlFor="feed-budget">{tf.monthlyBudget}</label>
          <input id="feed-budget" className="feed-number" type="number" min={0} max={100000} value={budget} onChange={(e) => setBudget(e.target.value)} />
        </div>
        <div className="feed-row">
          <label htmlFor="feed-cap">{tf.hourlyCap}</label>
          <input id="feed-cap" className="feed-number" type="number" min={1} max={600} value={cap} onChange={(e) => setCap(e.target.value)} />
        </div>
        <div className="feed-row">
          <span className="feed-hint">{note}</span>
          <Button variant="secondary" onClick={() => save({ monthly_budget: Number(budget), hourly_cap: Number(cap) })}>
            {tf.save}
          </Button>
        </div>
      </section>
    </>
  );
}
