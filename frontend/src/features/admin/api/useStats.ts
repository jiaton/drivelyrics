import { useCallback, useEffect, useState } from "react";
import { api } from "../../../lib/api";
import type { Stats } from "../types";

export function useStats() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    api<Stats>("/api/admin/stats")
      .then((body) => {
        setStats(body);
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(refresh, [refresh]);
  return { stats, error, refresh };
}
