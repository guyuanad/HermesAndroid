/** WebSocket client for Hermes real-time events */

import { API_BASE } from './endpoints';

export type HermesEventType =
  | 'text_delta'
  | 'tool_call_start'
  | 'tool_call_result'
  | 'tool_call_error'
  | 'session_reset'
  | 'model_changed'
  | 'memory_saved'
  | 'skill_created'
  | 'error';

export interface HermesEvent {
  type: HermesEventType;
  data: Record<string, any>;
}

export type EventHandler = (event: HermesEvent) => void;

export class HermesWebSocket {
  private ws: WebSocket | null = null;
  private listeners: Map<HermesEventType, Set<EventHandler>> = new Map();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private shouldReconnect = true;

  connect(path: string = '/api/events'): void {
    const wsUrl = API_BASE.replace(/^http/, 'ws') + path;
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log('Hermes WebSocket connected');
    };

    this.ws.onmessage = (event: WebSocketMessageEvent) => {
      try {
        const parsed: HermesEvent = JSON.parse(event.data);
        this.emit(parsed.type, parsed);
      } catch (e) {
        console.warn('Failed to parse WebSocket message', e);
      }
    };

    this.ws.onclose = () => {
      console.log('Hermes WebSocket closed');
      if (this.shouldReconnect) {
        this.reconnectTimer = setTimeout(() => this.connect(path), 3000);
      }
    };

    this.ws.onerror = (error) => {
      console.warn('Hermes WebSocket error', error);
    };
  }

  on(type: HermesEventType, handler: EventHandler): () => void {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, new Set());
    }
    this.listeners.get(type)!.add(handler);
    return () => this.listeners.get(type)?.delete(handler);
  }

  private emit(type: HermesEventType, event: HermesEvent): void {
    this.listeners.get(type)?.forEach((handler) => handler(event));
  }

  send(data: Record<string, any>): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  disconnect(): void {
    this.shouldReconnect = false;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
    }
    this.ws?.close();
    this.ws = null;
  }
}

/** Singleton WebSocket instance */
export const hermesWS = new HermesWebSocket();
