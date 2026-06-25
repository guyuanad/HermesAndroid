import { API_BASE } from './endpoints';
import type { Session } from './types';

export const sessionsApi = {
  list: async (): Promise<Session[]> => {
    const res = await fetch(`${API_BASE}/api/sessions`);
    return res.json();
  },

  get: async (id: string): Promise<Session> => {
    const res = await fetch(`${API_BASE}/api/sessions/${id}`);
    return res.json();
  },

  create: async (title?: string): Promise<Session> => {
    const res = await fetch(`${API_BASE}/api/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: title || 'New Session' }),
    });
    return res.json();
  },

  delete: async (id: string): Promise<void> => {
    await fetch(`${API_BASE}/api/sessions/${id}`, { method: 'DELETE' });
  },

  search: async (query: string): Promise<Session[]> => {
    const res = await fetch(`${API_BASE}/api/sessions/search?q=${encodeURIComponent(query)}`);
    return res.json();
  },

  stats: async () => {
    const res = await fetch(`${API_BASE}/api/sessions/stats`);
    return res.json();
  },
};
