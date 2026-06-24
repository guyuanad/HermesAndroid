import axios, { AxiosInstance, AxiosError } from 'axios';
import { API_BASE } from './endpoints';

/** HTTP client for Hermes Python backend */
const client: AxiosInstance = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Response interceptor for error handling
client.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.code === 'ECONNREFUSED') {
      // Backend not ready yet
      console.warn('Hermes backend not available');
    }
    return Promise.reject(error);
  }
);

export default client;

/** Check if the backend is ready */
export async function isBackendReady(): Promise<boolean> {
  try {
    const res = await client.get('/api/status', { timeout: 3000 });
    return res.status === 200;
  } catch {
    return false;
  }
}

/** Wait for backend to be ready, with polling */
export async function waitForBackend(
  maxRetries = 60,
  intervalMs = 1000
): Promise<boolean> {
  for (let i = 0; i < maxRetries; i++) {
    if (await isBackendReady()) {
      return true;
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  return false;
}
