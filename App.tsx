import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  View,
  Text,
  TextInput,
  FlatList,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  StatusBar,
} from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';

// ---------------------------------------------------------------------------
// Simple state (no zustand, no navigation - just React state)
// ---------------------------------------------------------------------------

const API_BASE = 'http://127.0.0.1:9119';

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function apiGet(path: string) {
  const res = await fetch(`${API_BASE}${path}`);
  return res.json();
}

async function apiPost(path: string, body: any) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return res.json();
}

async function apiPut(path: string, body: any) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return res.json();
}

async function apiDelete(path: string, body?: any) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  return res.json();
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'tool';
  content: string;
  timestamp: string;
}

interface EnvVar {
  key: string;
  value: string;
  is_set: boolean;
}

// ---------------------------------------------------------------------------
// Colors (Material Design 3)
// ---------------------------------------------------------------------------

const C = {
  primary: '#6750A4',
  onPrimary: '#FFFFFF',
  primaryContainer: '#EADDFF',
  onPrimaryContainer: '#21005D',
  secondary: '#625B71',
  onSecondary: '#FFFFFF',
  surface: '#FFFBFE',
  onSurface: '#1C1B1F',
  onSurfaceVariant: '#49454F',
  background: '#FFFBFE',
  outline: '#79747E',
  outlineVariant: '#CAC4D0',
  error: '#B3261E',
  surfaceVariant: '#E7E0EC',
  tertiaryContainer: '#FFD8E4',
  onTertiaryContainer: '#31111D',
};

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------

type Screen = 'splash' | 'chat' | 'settings';

function App() {
  const [screen, setScreen] = useState<Screen>('splash');
  const [backendReady, setBackendReady] = useState(false);

  // Check backend
  useEffect(() => {
    let attempts = 0;
    const check = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/health`);
        if (res.ok) {
          setBackendReady(true);
          setScreen('chat');
          return;
        }
      } catch {}
      attempts++;
      if (attempts < 60) {
        setTimeout(check, 2000);
      }
    };
    check();
  }, []);

  if (screen === 'splash') {
    return (
      <View style={s.splash}>
        <StatusBar barStyle="light-content" backgroundColor={C.primary} />
        <Text style={s.splashTitle}>Hermes 智能助手</Text>
        <Text style={s.splashSub}>你的自我进化 AI 伙伴</Text>
        <ActivityIndicator size="large" color={C.onPrimary} style={{ marginTop: 40 }} />
        <Text style={s.splashStatus}>
          {backendReady ? '就绪！' : '正在启动 AI 引擎...'}
        </Text>
        {!backendReady && (
          <TouchableOpacity
            style={s.retryBtn}
            onPress={() => setScreen('chat')}
          >
            <Text style={s.retryBtnText}>跳过</Text>
          </TouchableOpacity>
        )}
      </View>
    );
  }

  if (screen === 'settings') {
    return <SettingsScreen onBack={() => setScreen('chat')} />;
  }

  return <ChatScreen onSettings={() => setScreen('settings')} />;
}

// ---------------------------------------------------------------------------
// Chat Screen
// ---------------------------------------------------------------------------

function ChatScreen({ onSettings }: { onSettings: () => void }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isStreaming) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    };
    const assistantMsg: Message = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
    };
    setMessages(prev => [...prev, userMsg, assistantMsg]);
    setInputText('');
    setIsStreaming(true);

    try {
      const controller = new AbortController();
      abortRef.current = controller;

      const response = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, message: text }),
        signal: controller.signal,
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let fullText = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        for (const line of chunk.split('\n')) {
          if (!line.startsWith('data: ')) continue;
          const dataStr = line.slice(6).trim();
          if (!dataStr) continue;
          try {
            const parsed = JSON.parse(dataStr);
            if (parsed.type === 'text_delta' && parsed.data?.text) {
              fullText += parsed.data.text;
              setMessages(prev => {
                const updated = [...prev];
                updated[updated.length - 1] = {
                  ...updated[updated.length - 1],
                  content: fullText,
                };
                return updated;
              });
            } else if (parsed.type === 'error' && parsed.data?.text) {
              fullText += (fullText ? '\n\n' : '') + `Error: ${parsed.data.text}`;
              setMessages(prev => {
                const updated = [...prev];
                updated[updated.length - 1] = {
                  ...updated[updated.length - 1],
                  content: fullText,
                };
                return updated;
              });
            }
          } catch {}
        }
      }
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        setMessages(prev => {
          const updated = [...prev];
          updated[updated.length - 1] = {
            ...updated[updated.length - 1],
            content: `Error: ${e.message}`,
          };
          return updated;
        });
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  }, [sessionId, isStreaming]);

  const stopStreaming = () => abortRef.current?.abort();

  const renderMessage = ({ item }: { item: Message }) => {
    const isUser = item.role === 'user';
    return (
      <View style={[s.msgBubble, isUser ? s.msgUser : s.msgAssistant]}>
        <Text style={[s.msgText, isUser ? s.msgUserText : s.msgAssistantText]}>
          {item.content || (isStreaming && !isUser ? '...' : '')}
        </Text>
      </View>
    );
  };

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <StatusBar barStyle="dark-content" backgroundColor={C.surface} />
      {/* Header */}
      <View style={s.header}>
        <Text style={s.headerTitle}>Hermes</Text>
        <TouchableOpacity onPress={onSettings} style={s.headerBtn}>
          <Text style={s.headerBtnText}>设置</Text>
        </TouchableOpacity>
      </View>

      {/* Messages */}
      <FlatList
        data={messages}
        renderItem={renderMessage}
        keyExtractor={item => item.id}
        contentContainerStyle={s.msgList}
        ListEmptyComponent={
          <View style={s.empty}>
            <Text style={s.emptyTitle}>Hermes 智能助手</Text>
            <Text style={s.emptySub}>开始对话吧</Text>
          </View>
        }
      />

      {/* Input */}
      <View style={s.inputBar}>
        <TextInput
          style={s.textInput}
          placeholder="输入消息..."
          placeholderTextColor={C.onSurfaceVariant}
          value={inputText}
          onChangeText={setInputText}
          multiline
          editable={!isStreaming}
        />
        <TouchableOpacity
          style={[s.sendBtn, !inputText.trim() && s.sendBtnDisabled]}
          onPress={() => isStreaming ? stopStreaming() : sendMessage(inputText.trim())}
          disabled={!inputText.trim() && !isStreaming}
        >
          <Text style={s.sendBtnText}>{isStreaming ? '■' : '↑'}</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

// ---------------------------------------------------------------------------
// Settings Screen
// ---------------------------------------------------------------------------

function SettingsScreen({ onBack }: { onBack: () => void }) {
  const [envVars, setEnvVars] = useState<EnvVar[]>([]);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [keyValue, setKeyValue] = useState('');

  useEffect(() => {
    apiGet('/api/env').then(setEnvVars).catch(() => {});
  }, []);

  const handleSave = async (key: string) => {
    if (!keyValue.trim()) return;
    await apiPut('/api/env', { key, value: keyValue.trim() });
    setEditingKey(null);
    setKeyValue('');
    const envs = await apiGet('/api/env');
    setEnvVars(envs);
  };

  const handleDelete = async (key: string) => {
    await apiDelete('/api/env', { key });
    const envs = await apiGet('/api/env');
    setEnvVars(envs);
  };

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <StatusBar barStyle="dark-content" backgroundColor={C.surface} />
      <View style={s.header}>
        <TouchableOpacity onPress={onBack} style={s.headerBtn}>
          <Text style={s.headerBtnText}>返回</Text>
        </TouchableOpacity>
        <Text style={s.headerTitle}>设置</Text>
        <View style={{ width: 60 }} />
      </View>

      <ScrollView style={s.settingsContent}>
        {/* API Keys */}
        <View style={s.settingsSection}>
          <Text style={s.sectionTitle}>API 密钥</Text>
          {envVars.map(env => (
            <View key={env.key} style={s.envRow}>
              <View style={s.envInfo}>
                <Text style={s.envKey}>{env.key}</Text>
                <Text style={s.envValue}>{env.is_set ? env.value : '未设置'}</Text>
              </View>
              <View style={s.envActions}>
                <TouchableOpacity
                  style={s.envBtn}
                  onPress={() => { setEditingKey(env.key); setKeyValue(''); }}
                >
                  <Text style={s.envBtnText}>{env.is_set ? '编辑' : '设置'}</Text>
                </TouchableOpacity>
                {env.is_set && (
                  <TouchableOpacity
                    style={[s.envBtn, s.envBtnDanger]}
                    onPress={() => handleDelete(env.key)}
                  >
                    <Text style={s.envBtnText}>删除</Text>
                  </TouchableOpacity>
                )}
              </View>
              {editingKey === env.key && (
                <View style={s.keyInputRow}>
                  <TextInput
                    style={s.keyInput}
                    placeholder={`输入 ${env.key}`}
                    placeholderTextColor={C.onSurfaceVariant}
                    value={keyValue}
                    onChangeText={setKeyValue}
                    secureTextEntry
                    autoCapitalize="none"
                  />
                  <TouchableOpacity style={s.saveBtn} onPress={() => handleSave(env.key)}>
                    <Text style={s.saveBtnText}>保存</Text>
                  </TouchableOpacity>
                  <TouchableOpacity onPress={() => setEditingKey(null)}>
                    <Text style={s.cancelBtnText}>取消</Text>
                  </TouchableOpacity>
                </View>
              )}
            </View>
          ))}
        </View>

        {/* About */}
        <View style={s.settingsSection}>
          <Text style={s.sectionTitle}>关于</Text>
          <View style={s.aboutRow}>
            <Text style={s.aboutLabel}>版本</Text>
            <Text style={s.aboutValue}>0.1.0-android</Text>
          </View>
          <View style={s.aboutRow}>
            <Text style={s.aboutLabel}>后端</Text>
            <Text style={s.aboutValue}>FastAPI + httpx</Text>
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: C.background },
  splash: {
    flex: 1, justifyContent: 'center', alignItems: 'center',
    backgroundColor: C.primary,
  },
  splashTitle: { fontSize: 32, fontWeight: '700', color: C.onPrimary },
  splashSub: { fontSize: 16, color: C.onPrimary, opacity: 0.8, marginTop: 8 },
  splashStatus: { fontSize: 12, color: C.onPrimary, opacity: 0.6, marginTop: 16 },
  retryBtn: {
    marginTop: 24, paddingHorizontal: 24, paddingVertical: 8,
    borderRadius: 100, backgroundColor: 'rgba(255,255,255,0.2)',
  },
  retryBtnText: { fontSize: 14, color: C.onPrimary, fontWeight: '600' },

  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 12,
    backgroundColor: C.surface, borderBottomWidth: 1, borderBottomColor: C.outlineVariant,
  },
  headerTitle: { fontSize: 20, fontWeight: '700', color: C.onSurface },
  headerBtn: { padding: 8 },
  headerBtnText: { fontSize: 14, color: C.primary, fontWeight: '600' },

  msgList: { padding: 16, paddingBottom: 24 },
  msgBubble: {
    maxWidth: '80%', paddingHorizontal: 16, paddingVertical: 10,
    borderRadius: 20, marginBottom: 8,
  },
  msgUser: { alignSelf: 'flex-end', backgroundColor: C.primary },
  msgAssistant: { alignSelf: 'flex-start', backgroundColor: C.surfaceVariant },
  msgText: { fontSize: 15, lineHeight: 21 },
  msgUserText: { color: C.onPrimary },
  msgAssistantText: { color: C.onSurfaceVariant },

  empty: { alignItems: 'center', paddingTop: 100 },
  emptyTitle: { fontSize: 24, fontWeight: '700', color: C.onSurface },
  emptySub: { fontSize: 16, color: C.onSurfaceVariant, marginTop: 8 },

  inputBar: {
    flexDirection: 'row', alignItems: 'flex-end',
    paddingHorizontal: 12, paddingVertical: 8,
    borderTopWidth: 1, borderTopColor: C.outlineVariant,
    backgroundColor: C.surface,
  },
  textInput: {
    flex: 1, fontSize: 15, color: C.onSurface, maxHeight: 120,
    paddingHorizontal: 16, paddingVertical: 8,
    backgroundColor: C.surfaceVariant, borderRadius: 24,
  },
  sendBtn: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: C.primary, justifyContent: 'center', alignItems: 'center',
    marginLeft: 8,
  },
  sendBtnDisabled: { opacity: 0.4 },
  sendBtnText: { color: C.onPrimary, fontSize: 20, fontWeight: '700' },

  settingsContent: { flex: 1, padding: 16 },
  settingsSection: {
    backgroundColor: C.surface, borderRadius: 16, padding: 16, marginBottom: 12,
  },
  sectionTitle: { fontSize: 16, fontWeight: '600', color: C.primary, marginBottom: 12 },
  envRow: {
    borderTopWidth: 1, borderTopColor: C.outlineVariant, paddingVertical: 8,
  },
  envInfo: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  envKey: { fontSize: 14, fontWeight: '600', color: C.onSurface },
  envValue: { fontSize: 12, color: C.onSurfaceVariant },
  envActions: { flexDirection: 'row', gap: 8, marginTop: 4 },
  envBtn: {
    paddingHorizontal: 12, paddingVertical: 4, borderRadius: 8,
    backgroundColor: C.primary,
  },
  envBtnDanger: { backgroundColor: C.error },
  envBtnText: { fontSize: 12, color: C.onPrimary, fontWeight: '600' },
  keyInputRow: { flexDirection: 'row', alignItems: 'center', marginTop: 8, gap: 8 },
  keyInput: {
    flex: 1, fontSize: 14, color: C.onSurface,
    paddingHorizontal: 12, paddingVertical: 8,
    backgroundColor: C.surfaceVariant, borderRadius: 8,
  },
  saveBtn: {
    paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8,
    backgroundColor: C.primary,
  },
  saveBtnText: { fontSize: 12, color: C.onPrimary, fontWeight: '700' },
  cancelBtnText: { fontSize: 12, color: C.onSurfaceVariant },
  aboutRow: {
    flexDirection: 'row', justifyContent: 'space-between',
    paddingVertical: 8, borderTopWidth: 1, borderTopColor: C.outlineVariant,
  },
  aboutLabel: { fontSize: 14, color: C.onSurface },
  aboutValue: { fontSize: 14, color: C.onSurfaceVariant },
});

// ---------------------------------------------------------------------------
// Entry
// ---------------------------------------------------------------------------

function Root() {
  return (
    <SafeAreaProvider>
      <App />
    </SafeAreaProvider>
  );
}

export default Root;
