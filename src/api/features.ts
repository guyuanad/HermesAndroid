import client from './client';
import { ENDPOINTS } from './endpoints';
import type { Skill, CronJob, McpServer } from './types';

/** Skills API */
export const skillsApi = {
  list: () => client.get<Skill[]>(ENDPOINTS.SKILLS).then((r) => r.data),

  content: (name: string) =>
    client
      .get<Skill>(ENDPOINTS.SKILL_CONTENT, { params: { name } })
      .then((r) => r.data),

  toggle: (name: string, enabled: boolean) =>
    client
      .put(ENDPOINTS.SKILL_TOGGLE, { name, enabled })
      .then((r) => r.data),

  hubSearch: (query: string) =>
    client
      .get<Skill[]>(ENDPOINTS.SKILLS_HUB, { params: { q: query } })
      .then((r) => r.data),

  hubInstall: (name: string) =>
    client.post(ENDPOINTS.SKILLS_HUB_INSTALL, { name }).then((r) => r.data),
};

/** Cron API */
export const cronApi = {
  list: () => client.get<CronJob[]>(ENDPOINTS.CRON_JOBS).then((r) => r.data),

  get: (id: string) =>
    client.get<CronJob>(ENDPOINTS.CRON_DETAIL(id)).then((r) => r.data),

  create: (job: Partial<CronJob>) =>
    client.post<CronJob>(ENDPOINTS.CRON_JOBS, job).then((r) => r.data),

  update: (id: string, job: Partial<CronJob>) =>
    client.put(ENDPOINTS.CRON_DETAIL(id), job).then((r) => r.data),

  delete: (id: string) =>
    client.delete(ENDPOINTS.CRON_DETAIL(id)).then((r) => r.data),

  blueprints: () =>
    client.get(ENDPOINTS.CRON_BLUEPRINTS).then((r) => r.data),
};

/** MCP API */
export const mcpApi = {
  list: () =>
    client.get<McpServer[]>(ENDPOINTS.MCP_SERVERS).then((r) => r.data),

  add: (server: Partial<McpServer>) =>
    client.post(ENDPOINTS.MCP_SERVERS, server).then((r) => r.data),

  delete: (name: string) =>
    client
      .delete(ENDPOINTS.MCP_SERVERS, { data: { name } })
      .then((r) => r.data),

  catalog: () =>
    client.get(ENDPOINTS.MCP_CATALOG).then((r) => r.data),
};
