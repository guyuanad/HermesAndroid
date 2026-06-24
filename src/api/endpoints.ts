/** Hermes Agent API base URL - Python backend runs locally */
export const API_BASE = 'http://127.0.0.1:9119';

/** API endpoint constants */
export const ENDPOINTS = {
  // System
  STATUS: '/api/status',
  SYSTEM_STATS: '/api/system/stats',
  HEALTH: '/api/health',

  // Chat
  PTY_WS: '/api/pty',
  EVENTS_WS: '/api/events',
  WS: '/api/ws',

  // Sessions
  SESSIONS: '/api/sessions',
  SESSION_DETAIL: (id: string) => `/api/sessions/${id}`,
  SESSION_SEARCH: '/api/sessions/search',
  SESSION_STATS: '/api/sessions/stats',
  SESSION_EXPORT: (id: string) => `/api/sessions/${id}/export`,

  // Config
  CONFIG: '/api/config',
  CONFIG_RAW: '/api/config/raw',

  // Environment
  ENV: '/api/env',

  // Model
  MODEL_OPTIONS: '/api/model/options',
  MODEL_CURRENT: '/api/model/current',
  MODEL_SET: '/api/model/set',

  // Skills
  SKILLS: '/api/skills',
  SKILLS_HUB: '/api/skills/hub/search',
  SKILLS_HUB_INSTALL: '/api/skills/hub/install',
  SKILL_CONTENT: '/api/skills/content',
  SKILL_TOGGLE: '/api/skills/toggle',

  // Cron
  CRON_JOBS: '/api/cron/jobs',
  CRON_DETAIL: (id: string) => `/api/cron/jobs/${id}`,
  CRON_BLUEPRINTS: '/api/cron/blueprints',

  // MCP
  MCP_SERVERS: '/api/mcp/servers',
  MCP_CATALOG: '/api/mcp/catalog',

  // Memory
  MEMORY: '/api/memory',
  MEMORY_NOTES: '/api/memory/notes',
  MEMORY_PROFILE: '/api/memory/profile',

  // Files
  FILES: '/api/files',
  FS_LIST: '/api/fs/list',
  FS_READ: '/api/fs/read',

  // Messaging
  MESSAGING_STATUS: '/api/messaging/status',
  MESSAGING_CONFIG: '/api/messaging/config',

  // Analytics
  ANALYTICS_USAGE: '/api/analytics/usage',
  ANALYTICS_COST: '/api/analytics/cost',

  // Tools
  TOOLSETS: '/api/tools/toolsets',

  // Dashboard
  THEMES: '/api/dashboard/themes',
  PLUGINS: '/api/dashboard/plugins',

  // Credentials
  CREDENTIALS_POOL: '/api/credentials/pool',

  // Providers
  PROVIDERS_VALIDATE: '/api/providers/validate',
  PROVIDERS_OAUTH: (provider: string) => `/api/providers/oauth/${provider}`,

  // Ops
  OPS_CHECKPOINTS: '/api/ops/checkpoints',

  // Logs
  LOGS: '/api/logs',
} as const;
