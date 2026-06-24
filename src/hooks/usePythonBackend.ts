import { useEffect, useState } from 'react';
import { isBackendReady, waitForBackend } from '../api/client';
import { useSettingsStore } from '../store';

/** Hook to manage Python backend lifecycle */
export function usePythonBackend() {
  const { backendReady, setBackendReady } = useSettingsStore();
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    let cancelled = false;

    const check = async () => {
      const ready = await isBackendReady();
      if (!cancelled) {
        setBackendReady(ready);
        if (!ready) {
          // Start waiting
          const result = await waitForBackend(120, 1000);
          if (!cancelled) {
            setBackendReady(result);
          }
        }
      }
    };

    check();

    return () => {
      cancelled = true;
    };
  }, [retryCount, setBackendReady]);

  const retry = () => {
    setRetryCount((c) => c + 1);
  };

  return { backendReady, retry };
}
