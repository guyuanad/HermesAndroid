import { useCallback, useRef } from 'react';
import { useChatStore } from '../store';
import type { Message } from '../api/types';
import { API_BASE } from '../api/endpoints';

/** Hook for chat logic - uses SSE streaming from the Python backend */
export function useChat() {
  const { messages, currentSessionId, isStreaming, addMessage, setStreaming, setCurrentSession } =
    useChatStore();
  const abortRef = useRef<AbortController | null>(null);

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
        const controller = new AbortController();
        abortRef.current = controller;

        const response = await fetch(`${API_BASE}/api/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: currentSessionId,
            message: text,
          }),
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        // Read SSE stream
        const reader = response.body?.getReader();
        if (!reader) throw new Error('No response body');

        const decoder = new TextDecoder();
        let fullText = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          // Parse SSE events
          const lines = chunk.split('\n');
          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            const dataStr = line.slice(6).trim();
            if (!dataStr) continue;

            try {
              const parsed = JSON.parse(dataStr);
              if (parsed.type === 'text_delta' && parsed.data?.text) {
                fullText += parsed.data.text;
                useChatStore.getState().updateLastAssistant(fullText);
              } else if (parsed.type === 'error' && parsed.data?.text) {
                useChatStore.getState().updateLastAssistant(
                  (fullText ? fullText + '\n\n' : '') + `Error: ${parsed.data.text}`
                );
              } else if (parsed.type === 'done') {
                // Stream complete
              }
            } catch {
              // Ignore parse errors
            }
          }
        }

        // If we got a session_id from creating a new session, update it
        // The backend creates a session if none exists
        if (!currentSessionId) {
          // Fetch sessions to find the latest one
          try {
            const sessionsRes = await fetch(`${API_BASE}/api/sessions`);
            if (sessionsRes.ok) {
              const sessions = await sessionsRes.json();
              if (sessions.length > 0) {
                setCurrentSession(sessions[sessions.length - 1].id);
              }
            }
          } catch {
            // Ignore
          }
        }
      } catch (e: any) {
        if (e.name !== 'AbortError') {
          console.error('Failed to send message', e);
          useChatStore.getState().updateLastAssistant(
            'Error: Failed to connect to backend. Make sure the app has internet permission.'
          );
        }
      } finally {
        setStreaming(false);
        abortRef.current = null;
      }
    },
    [currentSessionId, isStreaming, addMessage, setStreaming, setCurrentSession]
  );

  const newSession = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'New Session' }),
      });
      if (res.ok) {
        const session = await res.json();
        setCurrentSession(session.id);
      }
    } catch (e) {
      console.error('Failed to create session', e);
    }
  }, [setCurrentSession]);

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return {
    messages,
    isStreaming,
    sendMessage,
    newSession,
    stopStreaming,
  };
}
