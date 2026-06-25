import { API_BASE } from './endpoints';

export const skillsApi = {
  list: async () => {
    const res = await fetch(`${API_BASE}/api/skills`);
    return res.json();
  },
  hubSearch: async (query: string) => {
    const res = await fetch(`${API_BASE}/api/skills/hub/search?q=${encodeURIComponent(query)}`);
    return res.json();
  },
};

export const cronApi = {
  list: async () => {
    const res = await fetch(`${API_BASE}/api/cron/jobs`);
    return res.json();
  },
};

export const mcpApi = {
  list: async () => {
    const res = await fetch(`${API_BASE}/api/mcp/servers`);
    return res.json();
  },
};
