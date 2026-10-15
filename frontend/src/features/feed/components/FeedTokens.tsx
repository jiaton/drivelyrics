import { useEffect, useState } from "react";
import { Button } from "../../../components/ui/Button";
import { CopyBox } from "../../../components/ui/CopyBox";
import { TextField } from "../../../components/ui/TextField";
import { fill } from "../../../i18n/rich";
import { useI18n } from "../../../i18n";
import { SOURCE_URL } from "../../landing/components/GitHubLink";
import { feedApi } from "../api/feedApi";
import type { FeedTokenInfo } from "../types";
import { ago } from "./ago";

const CLIENT_URL = SOURCE_URL.replace("github.com", "raw.githubusercontent.com") + "/main/docs/feed/feed_client.py";

function commands(token: string) {
  const base = window.location.origin;
  const body = '{"playing": true, "title": "Bohemian Rhapsody", "artist": "Queen", "duration_ms": 354000, "position_ms": 0}';
  return {
    curl: `curl -sS ${base}/api/feed/v1/now-playing \\\n  -H "Authorization: Bearer ${token}" -H "Content-Type: application/json" \\\n  -d '${body}'`,
    client: `curl -fsSLO ${CLIENT_URL}\nDRIVELYRICS_BASE=${base} DRIVELYRICS_TOKEN=${token} \\\n  python3 feed_client.py --command "./read-player.sh"`,
  };
}

/** Create / list / revoke push tokens. A new token is shown once, with commands to try it. */
export function FeedTokens({ onChanged }: { onChanged: () => void }) {
  const { t } = useI18n();
  const tf = t.app.feed;
  const [tokens, setTokens] = useState<FeedTokenInfo[]>([]);
  const [name, setName] = useState(tf.tokenNameDefault);
  const [created, setCreated] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => feedApi.tokens().then(setTokens).catch((err: Error) => setError(err.message));
  useEffect(() => {
    load();
  }, []);

  const create = () => {
    setError(null);
    feedApi
      .createToken(name.trim() || tf.tokenNameDefault)
      .then((body) => {
        setCreated(body.token);
        load();
        onChanged();
      })
      .catch((err: Error) => setError(err.message));
  };

  const revoke = (token: FeedTokenInfo) => {
    if (!window.confirm(tf.revokeConfirm)) return;
    feedApi
      .revokeToken(token.id)
      .then(() => {
        load();
        onChanged();
      })
      .catch((err: Error) => setError(err.message));
  };

  const cmd = created ? commands(created) : null;
  return (
    <section className="feed-section">
      <h2>{tf.tokens}</h2>
      <p className="feed-hint">{tf.tokensHint}</p>
      {tokens.map((token) => (
        <div key={token.id} className="feed-token">
          <div>
            <div>
              {token.name} <code className="feed-token-meta">{token.prefix}…</code>
            </div>
            <div className="feed-token-meta">
              {fill(tf.tokenMeta, {
                created: new Date(token.created_at * 1000).toLocaleDateString(),
                used: token.last_used_at ? fill(tf.lastUsed, { ago: ago(tf, token.last_used_at) }) : tf.neverUsed,
              })}
            </div>
          </div>
          <Button variant="ghost" onClick={() => revoke(token)}>
            {tf.revoke}
          </Button>
        </div>
      ))}
      {cmd ? (
        <div className="feed-reveal">
          <span>{tf.newToken}</span>
          <CopyBox value={created!} />
          <span className="feed-hint">{tf.tryIt}</span>
          <CopyBox value={cmd.curl} multiline />
          <span className="feed-hint">{tf.runClient}</span>
          <CopyBox value={cmd.client} multiline />
        </div>
      ) : null}
      <div className="feed-row" style={{ alignItems: "flex-end" }}>
        <div style={{ flex: 1, minWidth: "12rem" }}>
          <TextField label={tf.tokenName} value={name} maxLength={40} onChange={(e) => setName(e.target.value)} />
        </div>
        <Button onClick={create}>{tf.create}</Button>
      </div>
      {error ? <p className="feed-warning">{error}</p> : null}
    </section>
  );
}
