import { create } from 'zustand';
import type { Session, Message, HermesConfig, SystemStatus } from '../api/types';

interface ChatState {
  messages: Message[];
  currentSessionId: string | null;
  isStreaming: boolean;
  addMessage: (message: Message) => void;
  updateLastAssistant: (content: string) => void;
  setMessages: (messages: Message[]) => void;
  setCurrentSession: (id: string | null) => void;
  setStreaming: (streaming: boolean) => void;
  clearMessages: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  currentSessionId: null,
  isStreaming: false,

  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),

  updateLastAssistant: (content) =>
    set((state) => {
      const msgs = [...state.messages];
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].role === 'assistant') {
          msgs[i] = { ...msgs[i], content };
          break;
        }
      }
      return { messages: msgs };
    }),

  setMessages: (messages) => set({ messages }),

  setCurrentSession: (id) =>
    set({ currentSessionId: id, messages: [] }),

  setStreaming: (streaming) => set({ isStreaming: streaming }),

  clearMessages: () => set({ messages: [] }),
}));

interface SessionState {
  sessions: Session[];
  loading: boolean;
  setSessions: (sessions: Session[]) => void;
  setLoading: (loading: boolean) => void;
}

export const useSessionStore = create<SessionState>((set) => ({
  sessions: [],
  loading: false,

  setSessions: (sessions) => set({ sessions }),
  setLoading: (loading) => set({ loading }),
}));

interface SettingsState {
  config: HermesConfig | null;
  systemStatus: SystemStatus | null;
  backendReady: boolean;
  setConfig: (config: HermesConfig) => void;
  setSystemStatus: (status: SystemStatus) => void;
  setBackendReady: (ready: boolean) => void;
}

export const useSettingsStore = create<SettingsState>((set) => ({
  config: null,
  systemStatus: null,
  backendReady: false,

  setConfig: (config) => set({ config }),
  setSystemStatus: (status) => set({ systemStatus: status }),
  setBackendReady: (ready) => set({ backendReady: ready }),
}));
