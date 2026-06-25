import { API_BASE } from './endpoints';

export const configApi = {
  get: async () => {
    const res = await fetch(`${API_BASE}/api/config`);
    return res.json();
  },
  update: async (config: Record<string, unknown>) => {
    const res = await fetch(`${API_BASE}/api/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });
    return res.json();
  },
};

export const envApi = {
  get: async () => {
    const res = await fetch(`${API_BASE}/api/env`);
    return res.json();
  },
  set: async (key: string, value: string) => {
    const res = await fetch(`${API_BASE}/api/env`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key, value }),
    });
    return res.json();
  },
  delete: async (key: string) => {
    const res = await fetch(`${API_BASE}/api/env`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key }),
    });
    return res.json();
  },
};

export const modelApi = {
  options: async () => {
    const res = await fetch(`${API_BASE}/api/model/options`);
    return res.json();
  },
  current: async () => {
    const res = await fetch(`${API_BASE}/api/model/current`);
    return res.json();
  },
  set: async (model: string, provider: string) => {
    const res = await fetch(`${API_BASE}/api/model/set`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model, provider }),
    });
    return res.json();
  },
};

export const systemApi = {
  stats: async () => {
    const res = await fetch(`${API_BASE}/api/system/stats`);
    return res.json();
  },
  status: async () => {
    const res = await fetch(`${API_BASE}/api/status`);
    return res.json();
  },
};
