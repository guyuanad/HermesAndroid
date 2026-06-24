/** Shared API types */

export interface Session {
  id: string;
  title: string;
  model: string;
  provider: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  token_count: number;
  preview?: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  timestamp: string;
  model?: string;
  tool_calls?: ToolCall[];
}

export interface ToolCall {
  id: string;
  name: string;
  args: Record<string, any>;
  result?: string;
  status: 'running' | 'completed' | 'error';
}

export interface ModelOption {
  id: string;
  name: string;
  provider: string;
  context_length: number;
  supports_vision: boolean;
  supports_tools: boolean;
}

export interface Skill {
  name: string;
  description: string;
  enabled: boolean;
  content?: string;
  source: 'local' | 'hub';
}

export interface CronJob {
  id: string;
  name: string;
  schedule: string;
  prompt: string;
  enabled: boolean;
  last_run?: string;
  next_run?: string;
}

export interface McpServer {
  name: string;
  command: string;
  args: string[];
  enabled: boolean;
  status: 'connected' | 'disconnected' | 'error';
}

export interface HermesConfig {
  model: {
    default: string;
    provider: string;
  };
  agent: {
    max_turns: number;
    reasoning_effort: string;
  };
  compression: {
    enabled: boolean;
    threshold: number;
  };
  memory: {
    memory_enabled: boolean;
    user_profile_enabled: boolean;
    nudge_interval: number;
  };
  session_reset: {
    mode: string;
    idle_minutes: number;
  };
  skills: {
    creation_nudge_interval: number;
  };
  terminal: {
    backend: string;
  };
}

export interface SystemStatus {
  status: string;
  version: string;
  uptime: number;
  active_sessions: number;
  gateway_status: Record<string, string>;
}

export interface EnvVar {
  key: string;
  value: string;
  is_set: boolean;
}

export interface UsageStats {
  total_tokens: number;
  total_cost: number;
  sessions_count: number;
  messages_count: number;
  by_model: Record<string, { tokens: number; cost: number }>;
}
