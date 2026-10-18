/**
 * The last answers the server gave, kept on this device so the first screen can be
 * drawn before the network answers (a car's connection can take seconds). Never the
 * source of truth: every cached value is re-fetched at once and replaced. Cleared on
 * sign-out, account deletion and any 401, so a stale "signed in" can't loop.
 */
const PREFIX = "cache:";

export function readCache<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(PREFIX + key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

export function writeCache(key: string, value: unknown): void {
  try {
    localStorage.setItem(PREFIX + key, JSON.stringify(value));
  } catch {
    /* storage full or disabled: just no head start next time */
  }
}

export function clearCache(): void {
  try {
    for (const key of Object.keys(localStorage)) if (key.startsWith(PREFIX)) localStorage.removeItem(key);
  } catch {
    /* nothing to clear */
  }
}
