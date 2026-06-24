import client from './client';
import { ENDPOINTS } from './endpoints';
import type { HermesConfig, EnvVar, ModelOption, SystemStatus } from './types';

/** Config API */
export const configApi = {
  get: () => client.get<HermesConfig>(ENDPOINTS.CONFIG).then((r) => r.data),

  update: (config: Partial<HermesConfig>) =>
    client.put(ENDPOINTS.CONFIG, config).then((r) => r.data),

  getRaw: () => client.get<string>(ENDPOINTS.CONFIG_RAW).then((r) => r.data),
};

/** Environment / API Keys API */
export const envApi = {
  get: () => client.get<EnvVar[]>(ENDPOINTS.ENV).then((r) => r.data),

  set: (key: string, value: string) =>
    client.put(ENDPOINTS.ENV, { key, value }).then((r) => r.data),

  delete: (key: string) =>
    client.delete(ENDPOINTS.ENV, { data: { key } }).then((r) => r.data),
};

/** Model API */
export const modelApi = {
  options: () =>
    client.get<ModelOption[]>(ENDPOINTS.MODEL_OPTIONS).then((r) => r.data),

  current: () =>
    client.get(ENDPOINTS.MODEL_CURRENT).then((r) => r.data),

  set: (model: string, provider?: string) =>
    client.post(ENDPOINTS.MODEL_SET, { model, provider }).then((r) => r.data),
};

/** System API */
export const systemApi = {
  status: () =>
    client.get<SystemStatus>(ENDPOINTS.STATUS).then((r) => r.data),

  stats: () => client.get(ENDPOINTS.SYSTEM_STATS).then((r) => r.data),
};
