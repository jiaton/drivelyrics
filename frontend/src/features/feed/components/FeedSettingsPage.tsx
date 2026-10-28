import { useCallback, useEffect, useState } from "react";
import { Button } from "../../../components/ui/Button";
import { Page } from "../../../components/ui/Page";
import { rich } from "../../../i18n/rich";
import { useI18n } from "../../../i18n";
import { navigate } from "../../../lib/nav";
import { SOURCE_URL } from "../../landing/components/GitHubLink";
import type { Sources, SourceName } from "../../now-playing/api/useSources";
import { feedApi } from "../api/feedApi";
import type { FeedSettings, FeedStatus } from "../types";
import { FeedSchedule } from "./FeedSchedule";
import { FeedStatusPanel } from "./FeedStatusPanel";
import { FeedTokens } from "./FeedTokens";
import { FeedWebhook } from "./FeedWebhook";
import "./feed.css";

const STATUS_EVERY_MS = 3000;
const DOCS_URL = `${SOURCE_URL}/blob/main/docs/feed.md`;
const BLUEPRINT_URL = `${DOCS_URL}#home-assistant-blueprint`;
const BLUEPRINT_IMPORT_URL = `https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=${encodeURIComponent(`${SOURCE_URL}/blob/main/docs/feed/homeassistant/drivelyrics_feed.yaml`)}`;

/**
 * /feed: the now-playing feed — tokens, when fetches are sent, limits, the optional
 * webhook, and a live status for debugging one's own side. Best done on a computer.
 */
export function FeedSettingsPage({
  sources,
  onSourcesChanged,
  selectSource,
}: {
  sources: Sources;
  onSourcesChanged: () => void;
  selectSource: (source: SourceName) => Promise<void>;
}) {
  const { t } = useI18n();
  const tf = t.app.feed;
  const [status, setStatus] = useState<FeedStatus | null>(null);
  const [settings, setSettings] = useState<FeedSettings | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadStatus = useCallback(() => {
    feedApi.status().then(setStatus).catch((err: Error) => setError(err.message));
  }, []);
  const loadSettings = useCallback(() => {
    feedApi.settings().then(setSettings).catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    loadStatus();
    loadSettings();
    const id = window.setInterval(loadStatus, STATUS_EVERY_MS);
    return () => window.clearInterval(id);
  }, [loadStatus, loadSettings]);

  const changed = () => {
    loadStatus();
    loadSettings();
    onSourcesChanged();
  };

  return (
    <Page width={720}>
      <div className="feed-row">
        <Button variant="ghost" onClick={() => navigate("/")}>
          {tf.back}
        </Button>
        <a href={DOCS_URL} target="_blank" rel="noreferrer" style={{ color: "var(--color-accent)" }}>
          {tf.docs}
        </a>
        <a href={BLUEPRINT_URL} target="_blank" rel="noreferrer" style={{ color: "var(--color-accent)" }}>
          {tf.blueprint}
        </a>
        <a href={BLUEPRINT_IMPORT_URL} target="_blank" rel="noreferrer" style={{ color: "var(--color-accent)" }}>
          {tf.blueprintImport}
        </a>
      </div>
      <h1 style={{ margin: 0 }}>{tf.title}</h1>
      <p className="feed-hint">{rich(tf.intro)}</p>
      {sources.feed_enabled ? (
        sources.effective === "feed" ? (
          <p className="feed-status-line" style={{ color: "var(--color-accent)" }}>
            {tf.sourceOn}
          </p>
        ) : (
          <div className="feed-row">
            <span className="feed-hint">{tf.sourceOff}</span>
            <Button variant="secondary" onClick={() => selectSource("feed").catch((err: Error) => setError(err.message))}>
              {tf.useFeed}
            </Button>
          </div>
        )
      ) : null}
      {error ? <p className="feed-warning">{error}</p> : null}
      <section className="feed-section">
        <h2>{tf.status}</h2>
        {status ? <FeedStatusPanel status={status} /> : null}
      </section>
      <FeedTokens onChanged={changed} />
      {settings ? <FeedSchedule settings={settings} onSaved={setSettings} /> : null}
      {settings ? <FeedWebhook settings={settings} onChanged={changed} /> : null}
    </Page>
  );
}
