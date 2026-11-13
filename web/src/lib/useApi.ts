import { useCallback, useEffect, useRef, useState } from 'react';

export interface AsyncState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
}

interface Options {
  pollMs?: number;
  enabled?: boolean;
}

/**
 * Small data-loading hook with explicit polling. Polling never flashes the
 * loading skeleton; it only replaces data when a request succeeds.
 */
export function useApi<T>(
  loader: () => Promise<T>,
  deps: unknown[],
  options: Options = {},
): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;
  const mounted = useRef(true);
  const enabled = options.enabled ?? true;
  const pollMs = options.pollMs ?? 0;

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const run = useCallback(
    async (showLoading: boolean) => {
      if (!enabled) {
        setLoading(false);
        return;
      }
      if (showLoading) setLoading(true);
      try {
        const result = await loaderRef.current();
        if (mounted.current) {
          setData(result);
          setError(null);
        }
      } catch (caught) {
        if (mounted.current) {
          setError(caught instanceof Error ? caught.message : String(caught));
        }
      } finally {
        if (mounted.current) setLoading(false);
      }
    },
    [enabled],
  );

  useEffect(() => {
    void run(true);
    // The dependency list is supplied by the caller to refetch on key changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run, tick, ...deps]);

  useEffect(() => {
    if (!pollMs || !enabled) return;
    const interval = window.setInterval(() => {
      void run(false);
    }, pollMs);
    return () => window.clearInterval(interval);
  }, [pollMs, enabled, run]);

  const reload = useCallback(() => setTick((current) => current + 1), []);

  return { data, error, loading, reload };
}
