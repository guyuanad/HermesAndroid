import client from './client';
import { ENDPOINTS } from './endpoints';
import type { Session, Message } from './types';

/** Session API */
export const sessionsApi = {
  list: () => client.get<Session[]>(ENDPOINTS.SESSIONS).then((r) => r.data),

  get: (id: string) =>
    client.get<Session>(ENDPOINTS.SESSION_DETAIL(id)).then((r) => r.data),

  create: (title?: string) =>
    client
      .post<Session>(ENDPOINTS.SESSIONS, { title })
      .then((r) => r.data),

  delete: (id: string) =>
    client.delete(ENDPOINTS.SESSION_DETAIL(id)).then((r) => r.data),

  search: (query: string) =>
    client
      .get<Session[]>(ENDPOINTS.SESSION_SEARCH, { params: { q: query } })
      .then((r) => r.data),

  export: (id: string) =>
    client.get(ENDPOINTS.SESSION_EXPORT(id)).then((r) => r.data),

  stats: () => client.get(ENDPOINTS.SESSION_STATS).then((r) => r.data),
};
