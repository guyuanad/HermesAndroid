import { API_BASE } from './endpoints';

/** Check if the Python backend is ready */
export async function isBackendReady(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/health`, { method: 'GET' });
    return res.ok;
  } catch {
    return false;
  }
}

/** Wait for backend to become ready */
export async function waitForBackend(
  maxRetries: number = 120,
  intervalMs: number = 1000,
): Promise<boolean> {
  for (let i = 0; i < maxRetries; i++) {
    if (await isBackendReady()) {
      return true;
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  return false;
}
