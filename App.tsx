import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  View,
  Text,
  TextInput,
  FlatList,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  Platform,
  ActivityIndicator,
  StatusBar,
  Modal,
  Alert,
} from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';

// ---------------------------------------------------------------------------
// Config
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
// SSE stream via XHR (React Native compatible)
// ---------------------------------------------------------------------------

function parseSSEChunks(allData: string, startIndex: number): { events: any[]; newIndex: number } {
  const events: any[] = [];
  const chunk = allData.substring(startIndex);
  for (const line of chunk.split('\n')) {
    if (!line.startsWith('data: ')) continue;
    const dataStr = line.slice(6).trim();
    if (!dataStr) continue;
    try {
      events.push(JSON.parse(dataStr));
    } catch {}
  }
  return { events, newIndex: allData.length };
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
}

interface Session {
  id: string;
  title: string;
  message_count: number;
  updated_at: string;
  preview?: string;
}

interface ModelOption {
  id: string;
  name: string;
  provider: string;
  context_length: number;
  supports_vision: boolean;
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
  disabledBg: '#E0E0E0',
  disabledText: '#9E9E9E',
};

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------

type Screen = 'splash' | 'chat' | 'settings' | 'sessions';

function App() {
  const [screen, setScreen] = useState<Screen>('splash');
  const [backendReady, setBackendReady] = useState(false);
  const [currentModel, setCurrentModel] = useState('');
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [systemPrompt, setSystemPrompt] = useState('');

  // Check backend & load initial data
  useEffect(() => {
    let attempts = 0;
    const check = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/health`);
        if (res.ok) {
          setBackendReady(true);
          setScreen('chat');
          // Load current model
          try {
            const mc = await apiGet('/api/model/current');
            setCurrentModel(mc.model || '');
          } catch {}
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
          <TouchableOpacity style={s.retryBtn} onPress={() => setScreen('chat')}>
            <Text style={s.retryBtnText}>跳过</Text>
          </TouchableOpacity>
        )}
      </View>
    );
  }

  if (screen === 'settings') {
    return (
      <SettingsScreen
        onBack={() => setScreen('chat')}
        currentModel={currentModel}
        onModelChange={(m: string) => setCurrentModel(m)}
        systemPrompt={systemPrompt}
        onSystemPromptChange={setSystemPrompt}
      />
    );
  }

  if (screen === 'sessions') {
    return (
      <SessionsScreen
        currentSessionId={currentSessionId}
        onSelectSession={(id: string) => {
          setCurrentSessionId(id);
          setScreen('chat');
        }}
        onNewSession={() => {
          setCurrentSessionId(null);
          setScreen('chat');
        }}
        onBack={() => setScreen('chat')}
      />
    );
  }

  return (
    <ChatScreen
      onSettings={() => setScreen('settings')}
      onSessions={() => setScreen('sessions')}
      sessionId={currentSessionId}
      onSessionIdChange={setCurrentSessionId}
      currentModel={currentModel}
      systemPrompt={systemPrompt}
    />
  );
}

// ---------------------------------------------------------------------------
// Chat Screen
// ---------------------------------------------------------------------------

function ChatScreen({
  onSettings,
  onSessions,
  sessionId,
  onSessionIdChange,
  currentModel,
  systemPrompt,
}: {
  onSettings: () => void;
  onSessions: () => void;
  sessionId: string | null;
  onSessionIdChange: (id: string | null) => void;
  currentModel: string;
  systemPrompt: string;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<any>(null);
  const flatListRef = useRef<FlatList>(null);

  // Load session messages when session changes
  useEffect(() => {
    if (!sessionId) {
      setMessages([]);
      return;
    }
    apiGet(`/api/sessions/${sessionId}`).then((session: any) => {
      if (session.messages) {
        setMessages(session.messages.map((m: any) => ({
          id: m.id || Math.random().toString(),
          role: m.role,
          content: m.content,
          timestamp: m.timestamp,
        })));
      }
    }).catch(() => setMessages([]));
  }, [sessionId]);

  const sendMessage = useCallback((text: string) => {
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

    const xhr = new XMLHttpRequest();
    abortRef.current = { abort: () => xhr.abort() };

    let fullText = '';
    let processedIndex = 0;

    xhr.open('POST', `${API_BASE}/api/chat`);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.responseType = 'text';

    const processData = (data: string) => {
      for (const line of data.split('\n')) {
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
    };

    xhr.onprogress = () => {
      const responseText = xhr.responseText;
      if (responseText.length > processedIndex) {
        const newData = responseText.substring(processedIndex);
        processedIndex = responseText.length;
        processData(newData);
      }
    };

    xhr.onload = () => {
      const responseText = xhr.responseText;
      if (responseText.length > processedIndex) {
        processData(responseText.substring(processedIndex));
      }
      if (!fullText && xhr.status !== 200) {
        setMessages(prev => {
          const updated = [...prev];
          updated[updated.length - 1] = {
            ...updated[updated.length - 1],
            content: `Error: HTTP ${xhr.status}`,
          };
          return updated;
        });
      }
      setIsStreaming(false);
      abortRef.current = null;
    };

    xhr.onerror = () => {
      if (!fullText) {
        setMessages(prev => {
          const updated = [...prev];
          updated[updated.length - 1] = {
            ...updated[updated.length - 1],
            content: 'Error: 网络连接失败，请检查后端是否已启动',
          };
          return updated;
        });
      }
      setIsStreaming(false);
      abortRef.current = null;
    };

    xhr.onabort = () => {
      setIsStreaming(false);
      abortRef.current = null;
    };

    xhr.send(JSON.stringify({
      session_id: sessionId,
      message: text,
      system_prompt: systemPrompt || undefined,
    }));
  }, [sessionId, isStreaming, systemPrompt]);

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
        <TouchableOpacity onPress={onSessions} style={s.headerBtn}>
          <Text style={s.headerBtnText}>历史</Text>
        </TouchableOpacity>
        <View style={s.headerCenter}>
          <Text style={s.headerTitle} numberOfLines={1}>Hermes</Text>
          {currentModel ? <Text style={s.headerModel}>{currentModel}</Text> : null}
        </View>
        <TouchableOpacity onPress={onSettings} style={s.headerBtn}>
          <Text style={s.headerBtnText}>设置</Text>
        </TouchableOpacity>
      </View>

      {/* Messages */}
      <FlatList
        ref={flatListRef}
        data={messages}
        renderItem={renderMessage}
        keyExtractor={item => item.id}
        contentContainerStyle={s.msgList}
        onContentSizeChange={() => flatListRef.current?.scrollToEnd({ animated: false })}
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
          style={[s.sendBtn, !inputText.trim() && !isStreaming && s.sendBtnDisabled]}
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
// Sessions Screen
// ---------------------------------------------------------------------------

function SessionsScreen({
  currentSessionId,
  onSelectSession,
  onNewSession,
  onBack,
}: {
  currentSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  onBack: () => void;
}) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);

  const loadSessions = async () => {
    setLoading(true);
    try {
      const data = await apiGet('/api/sessions');
      setSessions(Array.isArray(data) ? data : []);
    } catch {}
    setLoading(false);
  };

  useEffect(() => { loadSessions(); }, []);

  const handleDelete = (id: string) => {
    Alert.alert('删除会话', '确定要删除这个会话吗？', [
      { text: '取消', style: 'cancel' },
      {
        text: '删除',
        style: 'destructive',
        onPress: async () => {
          await apiDelete(`/api/sessions/${id}`);
          loadSessions();
          if (currentSessionId === id) onNewSession();
        },
      },
    ]);
  };

  const renderItem = ({ item }: { item: Session }) => {
    const isCurrent = item.id === currentSessionId;
    return (
      <TouchableOpacity
        style={[s.sessionItem, isCurrent && s.sessionItemActive]}
        onPress={() => onSelectSession(item.id)}
        onLongPress={() => handleDelete(item.id)}
      >
        <View style={s.sessionInfo}>
          <Text style={s.sessionTitle} numberOfLines={1}>
            {isCurrent ? '● ' : ''}{item.title || '新会话'}
          </Text>
          <Text style={s.sessionMeta}>
            {item.message_count} 条消息 · {new Date(item.updated_at).toLocaleDateString()}
          </Text>
        </View>
      </TouchableOpacity>
    );
  };

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <StatusBar barStyle="dark-content" backgroundColor={C.surface} />
      <View style={s.header}>
        <TouchableOpacity onPress={onBack} style={s.headerBtn}>
          <Text style={s.headerBtnText}>返回</Text>
        </TouchableOpacity>
        <Text style={s.headerTitle}>会话历史</Text>
        <TouchableOpacity onPress={onNewSession} style={s.headerBtn}>
          <Text style={s.headerBtnText}>新建</Text>
        </TouchableOpacity>
      </View>

      {loading ? (
        <View style={s.loadingBox}>
          <ActivityIndicator size="large" color={C.primary} />
        </View>
      ) : sessions.length === 0 ? (
        <View style={s.empty}>
          <Text style={s.emptyTitle}>暂无会话</Text>
          <Text style={s.emptySub}>开始新对话吧</Text>
        </View>
      ) : (
        <FlatList
          data={sessions}
          renderItem={renderItem}
          keyExtractor={item => item.id}
          contentContainerStyle={s.sessionList}
        />
      )}
    </SafeAreaView>
  );
}

// ---------------------------------------------------------------------------
// Settings Screen
// ---------------------------------------------------------------------------

function SettingsScreen({
  onBack,
  currentModel,
  onModelChange,
  systemPrompt,
  onSystemPromptChange,
}: {
  onBack: () => void;
  currentModel: string;
  onModelChange: (model: string) => void;
  systemPrompt: string;
  onSystemPromptChange: (prompt: string) => void;
}) {
  const [models, setModels] = useState<ModelOption[]>([]);
  const [showModelPicker, setShowModelPicker] = useState(false);
  const [envVars, setEnvVars] = useState<any[]>([]);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [keyValue, setKeyValue] = useState('');
  const [editingPrompt, setEditingPrompt] = useState(false);
  const [promptDraft, setPromptDraft] = useState(systemPrompt);

  useEffect(() => {
    apiGet('/api/model/options').then(setModels).catch(() => {});
    apiGet('/api/env').then(setEnvVars).catch(() => {});
  }, []);

  const handleModelSelect = async (model: ModelOption) => {
    try {
      await apiPost('/api/model/set', { model: model.id, provider: model.provider });
      onModelChange(model.id);
      setShowModelPicker(false);
    } catch {}
  };

  const handleSaveEnv = async (key: string) => {
    if (!keyValue.trim()) return;
    await apiPut('/api/env', { key, value: keyValue.trim() });
    setEditingKey(null);
    setKeyValue('');
    const envs = await apiGet('/api/env');
    setEnvVars(envs);
  };

  const handleDeleteEnv = async (key: string) => {
    await apiDelete('/api/env', { key });
    const envs = await apiGet('/api/env');
    setEnvVars(envs);
  };

  const handleSavePrompt = () => {
    onSystemPromptChange(promptDraft);
    setEditingPrompt(false);
  };

  const currentModelName = models.find(m => m.id === currentModel)?.name || currentModel;

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
        {/* Model Selection */}
        <View style={s.settingsSection}>
          <Text style={s.sectionTitle}>模型选择</Text>
          <TouchableOpacity
            style={s.modelSelector}
            onPress={() => setShowModelPicker(true)}
          >
            <View>
              <Text style={s.modelSelectorLabel}>当前模型</Text>
              <Text style={s.modelSelectorValue}>{currentModelName || '未选择'}</Text>
            </View>
            <Text style={s.modelSelectorArrow}>›</Text>
          </TouchableOpacity>
        </View>

        {/* System Prompt */}
        <View style={s.settingsSection}>
          <Text style={s.sectionTitle}>系统提示词</Text>
          {editingPrompt ? (
            <View>
              <TextInput
                style={s.promptInput}
                placeholder="例如：你是一个专业的编程助手..."
                placeholderTextColor={C.onSurfaceVariant}
                value={promptDraft}
                onChangeText={setPromptDraft}
                multiline
                autoFocus
              />
              <View style={s.promptActions}>
                <TouchableOpacity style={s.saveBtn} onPress={handleSavePrompt}>
                  <Text style={s.saveBtnText}>保存</Text>
                </TouchableOpacity>
                <TouchableOpacity onPress={() => { setEditingPrompt(false); setPromptDraft(systemPrompt); }}>
                  <Text style={s.cancelBtnText}>取消</Text>
                </TouchableOpacity>
              </View>
            </View>
          ) : (
            <TouchableOpacity
              style={s.promptDisplay}
              onPress={() => { setPromptDraft(systemPrompt); setEditingPrompt(true); }}
            >
              <Text style={systemPrompt ? s.promptText : s.promptPlaceholder} numberOfLines={3}>
                {systemPrompt || '点击设置自定义系统提示词...'}
              </Text>
            </TouchableOpacity>
          )}
        </View>

        {/* API Keys */}
        <View style={s.settingsSection}>
          <Text style={s.sectionTitle}>API 密钥（高级）</Text>
          <Text style={s.sectionHint}>默认已内置 Agnes AI，如需使用其他服务请配置对应密钥</Text>
          {envVars.map((env: any) => (
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
                    onPress={() => handleDeleteEnv(env.key)}
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
                  <TouchableOpacity style={s.saveBtn} onPress={() => handleSaveEnv(env.key)}>
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
            <Text style={s.aboutValue}>0.2.0-android</Text>
          </View>
          <View style={s.aboutRow}>
            <Text style={s.aboutLabel}>后端</Text>
            <Text style={s.aboutValue}>FastAPI + httpx</Text>
          </View>
          <View style={s.aboutRow}>
            <Text style={s.aboutLabel}>默认模型</Text>
            <Text style={s.aboutValue}>Agnes 2.0 Flash</Text>
          </View>
        </View>
      </ScrollView>

      {/* Model Picker Modal */}
      <Modal visible={showModelPicker} animationType="slide" transparent>
        <View style={s.modalOverlay}>
          <View style={s.modalContent}>
            <View style={s.modalHeader}>
              <Text style={s.modalTitle}>选择模型</Text>
              <TouchableOpacity onPress={() => setShowModelPicker(false)}>
                <Text style={s.modalClose}>关闭</Text>
              </TouchableOpacity>
            </View>
            <FlatList
              data={models}
              keyExtractor={item => item.id}
              renderItem={({ item }) => (
                <TouchableOpacity
                  style={[s.modelItem, item.id === currentModel && s.modelItemActive]}
                  onPress={() => handleModelSelect(item)}
                >
                  <View>
                    <Text style={s.modelItemName}>{item.name}</Text>
                    <Text style={s.modelItemMeta}>
                      {item.provider} · {item.context_length >= 1000000
                        ? `${item.context_length / 1000000}M`
                        : `${item.context_length / 1000}K`} 上下文
                    </Text>
                  </View>
                  {item.id === currentModel && <Text style={s.modelItemCheck}>✓</Text>}
                </TouchableOpacity>
              )}
            />
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: C.background },

  // Splash
  splash: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: C.primary },
  splashTitle: { fontSize: 32, fontWeight: '700', color: C.onPrimary },
  splashSub: { fontSize: 16, color: C.onPrimary, opacity: 0.8, marginTop: 8 },
  splashStatus: { fontSize: 12, color: C.onPrimary, opacity: 0.6, marginTop: 16 },
  retryBtn: {
    marginTop: 24, paddingHorizontal: 24, paddingVertical: 8,
    borderRadius: 100, backgroundColor: 'rgba(255,255,255,0.2)',
  },
  retryBtnText: { fontSize: 14, color: C.onPrimary, fontWeight: '600' },

  // Header
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 12,
    backgroundColor: C.surface, borderBottomWidth: 1, borderBottomColor: C.outlineVariant,
  },
  headerCenter: { flex: 1, alignItems: 'center' },
  headerTitle: { fontSize: 20, fontWeight: '700', color: C.onSurface },
  headerModel: { fontSize: 11, color: C.onSurfaceVariant, marginTop: 2 },
  headerBtn: { padding: 8 },
  headerBtnText: { fontSize: 14, color: C.primary, fontWeight: '600' },

  // Messages
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

  // Input
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

  // Sessions
  sessionList: { padding: 16 },
  sessionItem: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: C.surface, borderRadius: 12, padding: 16, marginBottom: 8,
    borderWidth: 1, borderColor: C.outlineVariant,
  },
  sessionItemActive: { borderColor: C.primary, borderWidth: 2 },
  sessionInfo: { flex: 1 },
  sessionTitle: { fontSize: 15, fontWeight: '600', color: C.onSurface },
  sessionMeta: { fontSize: 12, color: C.onSurfaceVariant, marginTop: 4 },
  loadingBox: { flex: 1, justifyContent: 'center', alignItems: 'center' },

  // Settings
  settingsContent: { flex: 1, padding: 16 },
  settingsSection: {
    backgroundColor: C.surface, borderRadius: 16, padding: 16, marginBottom: 12,
  },
  sectionTitle: { fontSize: 16, fontWeight: '600', color: C.primary, marginBottom: 8 },
  sectionHint: { fontSize: 12, color: C.onSurfaceVariant, marginBottom: 12 },

  // Model Selector
  modelSelector: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: C.surfaceVariant, borderRadius: 12, padding: 14,
  },
  modelSelectorLabel: { fontSize: 12, color: C.onSurfaceVariant },
  modelSelectorValue: { fontSize: 15, fontWeight: '600', color: C.onSurface, marginTop: 2 },
  modelSelectorArrow: { fontSize: 24, color: C.onSurfaceVariant, fontWeight: '300' },

  // Model Picker Modal
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  modalContent: {
    backgroundColor: C.surface, borderTopLeftRadius: 24, borderTopRightRadius: 24,
    maxHeight: '80%', paddingBottom: 24,
  },
  modalHeader: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    padding: 16, borderBottomWidth: 1, borderBottomColor: C.outlineVariant,
  },
  modalTitle: { fontSize: 18, fontWeight: '700', color: C.onSurface },
  modalClose: { fontSize: 14, color: C.primary, fontWeight: '600' },
  modelItem: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 14,
    borderBottomWidth: 1, borderBottomColor: C.outlineVariant,
  },
  modelItemActive: { backgroundColor: C.primaryContainer },
  modelItemName: { fontSize: 15, fontWeight: '600', color: C.onSurface },
  modelItemMeta: { fontSize: 12, color: C.onSurfaceVariant, marginTop: 2 },
  modelItemCheck: { fontSize: 18, color: C.primary, fontWeight: '700' },

  // System Prompt
  promptDisplay: {
    backgroundColor: C.surfaceVariant, borderRadius: 12, padding: 14,
  },
  promptText: { fontSize: 14, color: C.onSurface, lineHeight: 20 },
  promptPlaceholder: { fontSize: 14, color: C.onSurfaceVariant },
  promptInput: {
    backgroundColor: C.surfaceVariant, borderRadius: 12, padding: 14,
    fontSize: 14, color: C.onSurface, minHeight: 80, lineHeight: 20,
    textAlignVertical: 'top',
  },
  promptActions: { flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 8 },

  // Env
  envRow: { borderTopWidth: 1, borderTopColor: C.outlineVariant, paddingVertical: 8 },
  envInfo: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  envKey: { fontSize: 14, fontWeight: '600', color: C.onSurface },
  envValue: { fontSize: 12, color: C.onSurfaceVariant },
  envActions: { flexDirection: 'row', gap: 8, marginTop: 4 },
  envBtn: { paddingHorizontal: 12, paddingVertical: 4, borderRadius: 8, backgroundColor: C.primary },
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

  // About
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
