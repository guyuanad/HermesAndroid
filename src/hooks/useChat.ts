import { useCallback, useRef } from 'react';
import { hermesWS } from '../api/websocket';
import { useChatStore } from '../store';
import type { Message } from '../api/types';
import client from '../api/client';
import { ENDPOINTS } from '../api/endpoints';

/** Hook for chat logic */
export function useChat() {
  const { messages, currentSessionId, isStreaming, addMessage, setStreaming, setCurrentSession } =
    useChatStore();
  const unsubscribers = useRef<Array<() => void>>([]);

  const connectWebSocket = useCallback(() => {
    hermesWS.connect('/api/events');

    const unsub1 = hermesWS.on('text_delta', (event) => {
      // Append text delta to last assistant message
      const store = useChatStore.getState();
      const lastMsg = store.messages[store.messages.length - 1];
      if (lastMsg?.role === 'assistant') {
        useChatStore.getState().updateLastAssistant(lastMsg.content + event.data.text);
      }
    });

    const unsub2 = hermesWS.on('tool_call_start', (event) => {
      addMessage({
        id: event.data.id || Date.now().toString(),
        role: 'tool',
        content: `Running: ${event.data.name}`,
        timestamp: new Date().toISOString(),
        tool_calls: [
          {
            id: event.data.id || '',
            name: event.data.name,
            args: event.data.args || {},
            status: 'running',
          },
        ],
      });
    });

    const unsub3 = hermesWS.on('tool_call_result', (event) => {
      addMessage({
        id: `result-${event.data.id || Date.now()}`,
        role: 'tool',
        content: event.data.result || '',
        timestamp: new Date().toISOString(),
      });
    });

    unsubscribers.current = [unsub1, unsub2, unsub3];
  }, [addMessage]);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || isStreaming) return;

      // Add user message
      const userMsg: Message = {
        id: Date.now().toString(),
        role: 'user',
        content: text,
        timestamp: new Date().toISOString(),
      };
      addMessage(userMsg);

      // Add placeholder assistant message
      const assistantMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: '',
        timestamp: new Date().toISOString(),
      };
      addMessage(assistantMsg);

      setStreaming(true);

      try {
        // Send to backend
        await client.post('/api/chat', {
          session_id: currentSessionId,
          message: text,
        });
      } catch (e) {
        console.error('Failed to send message', e);
        useChatStore.getState().updateLastAssistant('Error: Failed to send message');
      } finally {
        setStreaming(false);
      }
    },
    [currentSessionId, isStreaming, addMessage, setStreaming]
  );

  const newSession = useCallback(async () => {
    try {
      const res = await client.post(ENDPOINTS.SESSIONS, {});
      setCurrentSession(res.data.id);
    } catch (e) {
      console.error('Failed to create session', e);
    }
  }, [setCurrentSession]);

  const disconnect = useCallback(() => {
    unsubscribers.current.forEach((unsub) => unsub());
    hermesWS.disconnect();
  }, []);

  return {
    messages,
    isStreaming,
    sendMessage,
    newSession,
    connectWebSocket,
    disconnect,
  };
}
