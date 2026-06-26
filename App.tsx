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
// Types
// ---------------------------------------------------------------------------

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  tool_calls?: ToolCall[];
}

interface ToolCall {
  name: string;
  arguments: any;
  result_preview: string;
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

interface MemoryEntry {
  entry: string;
  category: string;
}

interface SkillInfo {
  name: string;
  description: string;
  version: string;
  category: string;
  emoji: string;
  file_count: number;
}

interface CronJob {
  id: string;
  name: string;
  schedule: string;
  schedule_description: string;
  prompt: string;
  paused: boolean;
  last_run: string | null;
  run_count: number;
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
  toolBg: '#E8F5E9',
  toolBorder: '#4CAF50',
};

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------

type Screen = 'splash' | 'chat' | 'settings' | 'sessions' | 'tools' | 'memory' | 'skills' | 'cron';

function App() {
  const [screen, setScreen] = useState<Screen>('splash');
  const [backendReady, setBackendReady] = useState(false);
  const [currentModel, setCurrentModel] = useState('');
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [systemPrompt, setSystemPrompt] = useState('');
  const [enableTools, setEnableTools] = useState(true);

  useEffect(() => {
    let attempts = 0;
    const check = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/health`);
        if (res.ok) {
          setBackendReady(true);
          setScreen('chat');
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
        enableTools={enableTools}
        onEnableToolsChange={setEnableTools}
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

  if (screen === 'tools') {
    return <ToolsScreen onBack={() => setScreen('chat')} />;
  }

  if (screen === 'memory') {
    return <MemoryScreen onBack={() => setScreen('chat')} />;
  }

  if (screen === 'skills') {
    return <SkillsScreen onBack={() => setScreen('chat')} />;
  }

  if (screen === 'cron') {
    return <CronScreen onBack={() => setScreen('chat')} />;
  }

  return (
    <ChatScreen
      onSettings={() => setScreen('settings')}
      onSessions={() => setScreen('sessions')}
      onTools={() => setScreen('tools')}
      sessionId={currentSessionId}
      onSessionIdChange={setCurrentSessionId}
      currentModel={currentModel}
      systemPrompt={systemPrompt}
      enableTools={enableTools}
    />
  );
}

// ---------------------------------------------------------------------------
// Chat Screen
// ---------------------------------------------------------------------------

function ChatScreen({
  onSettings,
  onSessions,
  onTools,
  sessionId,
  onSessionIdChange,
  currentModel,
  systemPrompt,
  enableTools,
}: {
  onSettings: () => void;
  onSessions: () => void;
  onTools: () => void;
  sessionId: string | null;
  onSessionIdChange: (id: string | null) => void;
  currentModel: string;
  systemPrompt: string;
  enableTools: boolean;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<any>(null);
  const flatListRef = useRef<FlatList>(null);

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
          tool_calls: m.tool_calls,
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
            content: 'Error: 网络连接失败',
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
      enable_tools: enableTools,
    }));
  }, [sessionId, isStreaming, systemPrompt, enableTools]);

  const stopStreaming = () => abortRef.current?.abort();

  const renderMessage = ({ item }: { item: Message }) => {
    const isUser = item.role === 'user';
    return (
      <View>
        <View style={[s.msgBubble, isUser ? s.msgUser : s.msgAssistant]}>
          <Text style={[s.msgText, isUser ? s.msgUserText : s.msgAssistantText]}>
            {item.content || (isStreaming && !isUser ? '...' : '')}
          </Text>
        </View>
        {item.tool_calls && item.tool_calls.length > 0 && (
          <View style={s.toolCallsContainer}>
            {item.tool_calls.map((tc: ToolCall, idx: number) => (
              <View key={idx} style={s.toolCallChip}>
                <Text style={s.toolCallName}>🔧 {tc.name}</Text>
                <Text style={s.toolCallResult} numberOfLines={2}>
                  {tc.result_preview}
                </Text>
              </View>
            ))}
          </View>
        )}
      </View>
    );
  };

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <StatusBar barStyle="dark-content" backgroundColor={C.surface} />
      <View style={s.header}>
        <TouchableOpacity onPress={onSessions} style={s.headerBtn}>
          <Text style={s.headerBtnText}>历史</Text>
        </TouchableOpacity>
        <View style={s.headerCenter}>
          <Text style={s.headerTitle} numberOfLines={1}>Hermes</Text>
          {currentModel ? <Text style={s.headerModel}>{currentModel}</Text> : null}
        </View>
        <View style={s.headerRight}>
          <TouchableOpacity onPress={onTools} style={s.headerBtnSmall}>
            <Text style={s.headerBtnIcon}>🔧</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={onSettings} style={s.headerBtnSmall}>
            <Text style={s.headerBtnIcon}>⚙</Text>
          </TouchableOpacity>
        </View>
      </View>

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
            <Text style={s.emptyHint}>支持工具调用、记忆、技能、定时任务</Text>
          </View>
        }
      />

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
// Tools Screen
// ---------------------------------------------------------------------------

function ToolsScreen({ onBack }: { onBack: () => void }) {
  const [tools, setTools] = useState<any[]>([]);
  const [toolsets, setToolsets] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiGet('/api/tools'),
      apiGet('/api/tools/toolsets'),
    ]).then(([t, ts]) => {
      setTools(Array.isArray(t) ? t : []);
      setToolsets(Array.isArray(ts) ? ts : []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <StatusBar barStyle="dark-content" backgroundColor={C.surface} />
      <View style={s.header}>
        <TouchableOpacity onPress={onBack} style={s.headerBtn}>
          <Text style={s.headerBtnText}>返回</Text>
        </TouchableOpacity>
        <Text style={s.headerTitle}>工具 & 功能</Text>
        <View style={{ width: 60 }} />
      </View>

      <ScrollView style={s.settingsContent}>
        {/* Feature Cards */}
        <Text style={s.sectionTitle}>核心功能</Text>
        <View style={s.featureGrid}>
          <TouchableOpacity
            style={s.featureCard}
            onPress={() => { /* navigate to memory screen - handled by parent */ }}
          >
            <Text style={s.featureEmoji}>🧠</Text>
            <Text style={s.featureName}>记忆系统</Text>
            <Text style={s.featureDesc}>AI 的持久记忆</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={s.featureCard}
            onPress={() => {}}
          >
            <Text style={s.featureEmoji}>📋</Text>
            <Text style={s.featureName}>任务管理</Text>
            <Text style={s.featureDesc}>待办事项追踪</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={s.featureCard}
            onPress={() => {}}
          >
            <Text style={s.featureEmoji}>🎯</Text>
            <Text style={s.featureName}>技能系统</Text>
            <Text style={s.featureDesc}>自定义技能扩展</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={s.featureCard}
            onPress={() => {}}
          >
            <Text style={s.featureEmoji}>⏰</Text>
            <Text style={s.featureName}>定时任务</Text>
            <Text style={s.featureDesc}>Cron 定时执行</Text>
          </TouchableOpacity>
        </View>

        {/* Tool List */}
        <Text style={s.sectionTitle}>已注册工具 ({tools.length})</Text>
        {loading ? (
          <ActivityIndicator size="large" color={C.primary} />
        ) : (
          tools.map((tool: any) => (
            <View key={tool.name} style={s.toolItem}>
              <View style={s.toolInfo}>
                <Text style={s.toolEmoji}>{tool.emoji || '⚙'}</Text>
                <View style={s.toolText}>
                  <Text style={s.toolName}>{tool.name}</Text>
                  <Text style={s.toolDesc} numberOfLines={2}>{tool.description}</Text>
                </View>
              </View>
            </View>
          ))
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

// ---------------------------------------------------------------------------
// Memory Screen
// ---------------------------------------------------------------------------

function MemoryScreen({ onBack }: { onBack: () => void }) {
  const [memory, setMemory] = useState<any>(null);
  const [newEntry, setNewEntry] = useState('');
  const [category, setCategory] = useState<'memory' | 'user'>('memory');

  const loadMemory = async () => {
    try {
      const data = await apiGet('/api/memory');
      setMemory(data);
    } catch {}
  };

  useEffect(() => { loadMemory(); }, []);

  const addMemory = async () => {
    if (!newEntry.trim()) return;
    await apiPost('/memory/add', { entry: newEntry.trim(), category });
    setNewEntry('');
    loadMemory();
  };

  const removeMemory = async (entry: string, cat: string) => {
    await apiPost('/memory/remove', { entry, category: cat });
    loadMemory();
  };

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <StatusBar barStyle="dark-content" backgroundColor={C.surface} />
      <View style={s.header}>
        <TouchableOpacity onPress={onBack} style={s.headerBtn}>
          <Text style={s.headerBtnText}>返回</Text>
        </TouchableOpacity>
        <Text style={s.headerTitle}>🧠 记忆管理</Text>
        <View style={{ width: 60 }} />
      </View>

      <ScrollView style={s.settingsContent}>
        {/* Add Entry */}
        <View style={s.settingsSection}>
          <Text style={s.sectionTitle}>添加记忆</Text>
          <View style={s.categoryRow}>
            <TouchableOpacity
              style={[s.categoryBtn, category === 'memory' && s.categoryBtnActive]}
              onPress={() => setCategory('memory')}
            >
              <Text style={category === 'memory' ? s.categoryBtnActiveText : s.categoryBtnText}>一般记忆</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[s.categoryBtn, category === 'user' && s.categoryBtnActive]}
              onPress={() => setCategory('user')}
            >
              <Text style={category === 'user' ? s.categoryBtnActiveText : s.categoryBtnText}>用户画像</Text>
            </TouchableOpacity>
          </View>
          <TextInput
            style={s.promptInput}
            placeholder="输入记忆内容..."
            placeholderTextColor={C.onSurfaceVariant}
            value={newEntry}
            onChangeText={setNewEntry}
            multiline
          />
          <TouchableOpacity style={s.saveBtn} onPress={addMemory}>
            <Text style={s.saveBtnText}>添加</Text>
          </TouchableOpacity>
        </View>

        {/* Memory Entries */}
        {memory?.memory_entries?.length > 0 && (
          <View style={s.settingsSection}>
            <Text style={s.sectionTitle}>一般记忆 ({memory.memory_count})</Text>
            {memory.memory_entries.map((entry: string, idx: number) => (
              <View key={idx} style={s.memEntry}>
                <Text style={s.memText}>{entry}</Text>
                <TouchableOpacity onPress={() => removeMemory(entry, 'memory')}>
                  <Text style={s.memDelete}>删除</Text>
                </TouchableOpacity>
              </View>
            ))}
          </View>
        )}

        {/* User Profile Entries */}
        {memory?.user_entries?.length > 0 && (
          <View style={s.settingsSection}>
            <Text style={s.sectionTitle}>用户画像 ({memory.user_count})</Text>
            {memory.user_entries.map((entry: string, idx: number) => (
              <View key={idx} style={s.memEntry}>
                <Text style={s.memText}>{entry}</Text>
                <TouchableOpacity onPress={() => removeMemory(entry, 'user')}>
                  <Text style={s.memDelete}>删除</Text>
                </TouchableOpacity>
              </View>
            ))}
          </View>
        )}

        {(!memory?.memory_entries?.length && !memory?.user_entries?.length) && (
          <View style={s.settingsSection}>
            <Text style={s.emptySub}>暂无记忆条目</Text>
            <Text style={s.emptyHint}>AI 会在对话中自动学习并保存记忆</Text>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

// ---------------------------------------------------------------------------
// Skills Screen
// ---------------------------------------------------------------------------

function SkillsScreen({ onBack }: { onBack: () => void }) {
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [newSkill, setNewSkill] = useState({ name: '', description: '', category: 'general', content: '' });

  const loadSkills = async () => {
    try {
      const data = await apiGet('/api/skills');
      const result = data?.result?.skills || data?.skills || data || [];
      setSkills(Array.isArray(result) ? result : []);
    } catch {
      setSkills([]);
    }
  };

  useEffect(() => { loadSkills(); }, []);

  const createSkill = async () => {
    if (!newSkill.name.trim()) return;
    await apiPost('/api/skills/manage', {
      action: 'create',
      ...newSkill,
    });
    setNewSkill({ name: '', description: '', category: 'general', content: '' });
    setShowCreate(false);
    loadSkills();
  };

  const deleteSkill = (name: string) => {
    Alert.alert('删除技能', `确定要删除技能 "${name}" 吗？`, [
      { text: '取消', style: 'cancel' },
      {
        text: '删除',
        style: 'destructive',
        onPress: async () => {
          await apiDelete(`/api/skills/${name}`);
          loadSkills();
        },
      },
    ]);
  };

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <StatusBar barStyle="dark-content" backgroundColor={C.surface} />
      <View style={s.header}>
        <TouchableOpacity onPress={onBack} style={s.headerBtn}>
          <Text style={s.headerBtnText}>返回</Text>
        </TouchableOpacity>
        <Text style={s.headerTitle}>🎯 技能管理</Text>
        <TouchableOpacity onPress={() => setShowCreate(true)} style={s.headerBtn}>
          <Text style={s.headerBtnText}>新建</Text>
        </TouchableOpacity>
      </View>

      <ScrollView style={s.settingsContent}>
        {skills.length === 0 ? (
          <View style={s.settingsSection}>
            <Text style={s.emptySub}>暂无技能</Text>
            <Text style={s.emptyHint}>AI 可以在对话中自动创建技能</Text>
          </View>
        ) : (
          skills.map((skill: SkillInfo) => (
            <View key={skill.name} style={s.skillItem}>
              <View style={s.skillInfo}>
                <Text style={s.skillEmoji}>{skill.emoji || '🎯'}</Text>
                <View style={s.skillText}>
                  <Text style={s.skillName}>{skill.name}</Text>
                  <Text style={s.skillDesc} numberOfLines={2}>{skill.description}</Text>
                  <Text style={s.skillMeta}>{skill.category} · v{skill.version} · {skill.file_count} 文件</Text>
                </View>
              </View>
              <TouchableOpacity onPress={() => deleteSkill(skill.name)}>
                <Text style={s.memDelete}>删除</Text>
              </TouchableOpacity>
            </View>
          ))
        )}
      </ScrollView>

      {/* Create Skill Modal */}
      <Modal visible={showCreate} animationType="slide" transparent>
        <View style={s.modalOverlay}>
          <View style={s.modalContent}>
            <View style={s.modalHeader}>
              <Text style={s.modalTitle}>创建技能</Text>
              <TouchableOpacity onPress={() => setShowCreate(false)}>
                <Text style={s.modalClose}>关闭</Text>
              </TouchableOpacity>
            </View>
            <ScrollView style={{ padding: 16 }}>
              <TextInput
                style={s.keyInput}
                placeholder="技能名称 (小写字母数字)"
                placeholderTextColor={C.onSurfaceVariant}
                value={newSkill.name}
                onChangeText={t => setNewSkill({ ...newSkill, name: t })}
                autoCapitalize="none"
              />
              <TextInput
                style={s.keyInput}
                placeholder="描述"
                placeholderTextColor={C.onSurfaceVariant}
                value={newSkill.description}
                onChangeText={t => setNewSkill({ ...newSkill, description: t })}
              />
              <TextInput
                style={[s.keyInput, { minHeight: 80 }]}
                placeholder="技能内容 (Markdown)"
                placeholderTextColor={C.onSurfaceVariant}
                value={newSkill.content}
                onChangeText={t => setNewSkill({ ...newSkill, content: t })}
                multiline
                textAlignVertical="top"
              />
              <TouchableOpacity style={s.saveBtn} onPress={createSkill}>
                <Text style={s.saveBtnText}>创建</Text>
              </TouchableOpacity>
            </ScrollView>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

// ---------------------------------------------------------------------------
// Cron Screen
// ---------------------------------------------------------------------------

function CronScreen({ onBack }: { onBack: () => void }) {
  const [jobs, setJobs] = useState<CronJob[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [newJob, setNewJob] = useState({ name: '', schedule: '', prompt: '' });

  const loadJobs = async () => {
    try {
      const data = await apiGet('/api/cron/jobs');
      setJobs(Array.isArray(data) ? data : []);
    } catch {
      setJobs([]);
    }
  };

  useEffect(() => { loadJobs(); }, []);

  const createJob = async () => {
    if (!newJob.name.trim() || !newJob.schedule.trim()) return;
    try {
      await apiPost('/api/cron/jobs', newJob);
      setNewJob({ name: '', schedule: '', prompt: '' });
      setShowCreate(false);
      loadJobs();
    } catch (e: any) {
      Alert.alert('错误', e.message || '创建失败');
    }
  };

  const togglePause = async (job: CronJob) => {
    const action = job.paused ? 'resume' : 'pause';
    await apiPost(`/api/cron/jobs/${job.id}/${action}`);
    loadJobs();
  };

  const deleteJob = (job: CronJob) => {
    Alert.alert('删除任务', `确定要删除 "${job.name}" 吗？`, [
      { text: '取消', style: 'cancel' },
      {
        text: '删除',
        style: 'destructive',
        onPress: async () => {
          await apiDelete(`/api/cron/jobs/${job.id}`);
          loadJobs();
        },
      },
    ]);
  };

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <StatusBar barStyle="dark-content" backgroundColor={C.surface} />
      <View style={s.header}>
        <TouchableOpacity onPress={onBack} style={s.headerBtn}>
          <Text style={s.headerBtnText}>返回</Text>
        </TouchableOpacity>
        <Text style={s.headerTitle}>⏰ 定时任务</Text>
        <TouchableOpacity onPress={() => setShowCreate(true)} style={s.headerBtn}>
          <Text style={s.headerBtnText}>新建</Text>
        </TouchableOpacity>
      </View>

      <ScrollView style={s.settingsContent}>
        {jobs.length === 0 ? (
          <View style={s.settingsSection}>
            <Text style={s.emptySub}>暂无定时任务</Text>
            <Text style={s.emptyHint}>创建定时任务让 AI 自动执行</Text>
          </View>
        ) : (
          jobs.map((job: CronJob) => (
            <View key={job.id} style={s.cronItem}>
              <View style={s.cronInfo}>
                <Text style={s.cronName}>
                  {job.paused ? '⏸' : '▶'} {job.name}
                </Text>
                <Text style={s.cronSchedule}>{job.schedule_description || job.schedule}</Text>
                {job.prompt ? (
                  <Text style={s.cronPrompt} numberOfLines={2}>{job.prompt}</Text>
                ) : null}
                <Text style={s.cronMeta}>
                  执行 {job.run_count} 次 · {job.last_run ? new Date(job.last_run).toLocaleString() : '未执行'}
                </Text>
              </View>
              <View style={s.cronActions}>
                <TouchableOpacity
                  style={[s.cronBtn, job.paused ? s.cronBtnResume : s.cronBtnPause]}
                  onPress={() => togglePause(job)}
                >
                  <Text style={s.cronBtnText}>{job.paused ? '恢复' : '暂停'}</Text>
                </TouchableOpacity>
                <TouchableOpacity onPress={() => deleteJob(job)}>
                  <Text style={s.memDelete}>删除</Text>
                </TouchableOpacity>
              </View>
            </View>
          ))
        )}
      </ScrollView>

      {/* Create Job Modal */}
      <Modal visible={showCreate} animationType="slide" transparent>
        <View style={s.modalOverlay}>
          <View style={s.modalContent}>
            <View style={s.modalHeader}>
              <Text style={s.modalTitle}>创建定时任务</Text>
              <TouchableOpacity onPress={() => setShowCreate(false)}>
                <Text style={s.modalClose}>关闭</Text>
              </TouchableOpacity>
            </View>
            <ScrollView style={{ padding: 16 }}>
              <TextInput
                style={s.keyInput}
                placeholder="任务名称"
                placeholderTextColor={C.onSurfaceVariant}
                value={newJob.name}
                onChangeText={t => setNewJob({ ...newJob, name: t })}
              />
              <TextInput
                style={s.keyInput}
                placeholder="Cron 表达式 (如 */5 * * * *)"
                placeholderTextColor={C.onSurfaceVariant}
                value={newJob.schedule}
                onChangeText={t => setNewJob({ ...newJob, schedule: t })}
                autoCapitalize="none"
              />
              <TextInput
                style={[s.keyInput, { minHeight: 80 }]}
                placeholder="执行提示词"
                placeholderTextColor={C.onSurfaceVariant}
                value={newJob.prompt}
                onChangeText={t => setNewJob({ ...newJob, prompt: t })}
                multiline
                textAlignVertical="top"
              />
              <TouchableOpacity style={s.saveBtn} onPress={createJob}>
                <Text style={s.saveBtnText}>创建</Text>
              </TouchableOpacity>
            </ScrollView>
          </View>
        </View>
      </Modal>
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
  enableTools,
  onEnableToolsChange,
}: {
  onBack: () => void;
  currentModel: string;
  onModelChange: (model: string) => void;
  systemPrompt: string;
  onSystemPromptChange: (prompt: string) => void;
  enableTools: boolean;
  onEnableToolsChange: (v: boolean) => void;
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

        {/* Tool Calling Toggle */}
        <View style={s.settingsSection}>
          <Text style={s.sectionTitle}>工具调用</Text>
          <TouchableOpacity
            style={s.toggleRow}
            onPress={() => onEnableToolsChange(!enableTools)}
          >
            <View>
              <Text style={s.toggleLabel}>启用工具调用</Text>
              <Text style={s.toggleDesc}>允许 AI 调用记忆、任务、技能等工具</Text>
            </View>
            <View style={[s.toggleIndicator, enableTools && s.toggleOn]}>
              <Text style={s.toggleText}>{enableTools ? '开' : '关'}</Text>
            </View>
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
            <Text style={s.aboutValue}>0.3.0-android</Text>
          </View>
          <View style={s.aboutRow}>
            <Text style={s.aboutLabel}>后端</Text>
            <Text style={s.aboutValue}>FastAPI + httpx + Tools</Text>
          </View>
          <View style={s.aboutRow}>
            <Text style={s.aboutLabel}>默认模型</Text>
            <Text style={s.aboutValue}>Agnes 2.0 Flash</Text>
          </View>
          <View style={s.aboutRow}>
            <Text style={s.aboutLabel}>工具系统</Text>
            <Text style={s.aboutValue}>记忆/任务/技能/定时</Text>
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
                      {item.supports_tools ? ' · 工具调用' : ''}
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
  headerRight: { flexDirection: 'row', gap: 4 },
  headerBtnSmall: { padding: 8 },
  headerBtnIcon: { fontSize: 18 },

  // Messages
  msgList: { padding: 16, paddingBottom: 24 },
  msgBubble: {
    maxWidth: '80%', paddingHorizontal: 16, paddingVertical: 10,
    borderRadius: 20, marginBottom: 4,
  },
  msgUser: { alignSelf: 'flex-end', backgroundColor: C.primary },
  msgAssistant: { alignSelf: 'flex-start', backgroundColor: C.surfaceVariant },
  msgText: { fontSize: 15, lineHeight: 21 },
  msgUserText: { color: C.onPrimary },
  msgAssistantText: { color: C.onSurfaceVariant },
  empty: { alignItems: 'center', paddingTop: 100 },
  emptyTitle: { fontSize: 24, fontWeight: '700', color: C.onSurface },
  emptySub: { fontSize: 16, color: C.onSurfaceVariant, marginTop: 8 },
  emptyHint: { fontSize: 12, color: C.onSurfaceVariant, marginTop: 4, opacity: 0.7 },

  // Tool calls
  toolCallsContainer: {
    flexDirection: 'row', flexWrap: 'wrap', gap: 4,
    marginTop: 4, marginBottom: 8, paddingHorizontal: 4,
  },
  toolCallChip: {
    backgroundColor: C.toolBg, borderRadius: 8, padding: 6,
    borderWidth: 1, borderColor: C.toolBorder,
    maxWidth: '80%',
  },
  toolCallName: { fontSize: 11, fontWeight: '600', color: '#2E7D32' },
  toolCallResult: { fontSize: 10, color: '#388E3C', marginTop: 2 },

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

  // Tools
  featureGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 16 },
  featureCard: {
    backgroundColor: C.surfaceVariant, borderRadius: 12, padding: 16,
    width: '48%', alignItems: 'center',
  },
  featureEmoji: { fontSize: 32, marginBottom: 4 },
  featureName: { fontSize: 14, fontWeight: '600', color: C.onSurface },
  featureDesc: { fontSize: 11, color: C.onSurfaceVariant, marginTop: 2 },
  toolItem: {
    backgroundColor: C.surface, borderRadius: 8, padding: 12, marginBottom: 6,
    borderWidth: 1, borderColor: C.outlineVariant,
  },
  toolInfo: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  toolEmoji: { fontSize: 20 },
  toolText: { flex: 1 },
  toolName: { fontSize: 14, fontWeight: '600', color: C.onSurface },
  toolDesc: { fontSize: 12, color: C.onSurfaceVariant, marginTop: 2 },

  // Memory
  categoryRow: { flexDirection: 'row', gap: 8, marginBottom: 8 },
  categoryBtn: {
    paddingHorizontal: 16, paddingVertical: 6, borderRadius: 16,
    backgroundColor: C.surfaceVariant,
  },
  categoryBtnActive: { backgroundColor: C.primary },
  categoryBtnText: { fontSize: 13, color: C.onSurfaceVariant },
  categoryBtnActiveText: { fontSize: 13, color: C.onPrimary, fontWeight: '600' },
  memEntry: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingVertical: 8, borderTopWidth: 1, borderTopColor: C.outlineVariant,
  },
  memText: { flex: 1, fontSize: 14, color: C.onSurface, marginRight: 8 },
  memDelete: { fontSize: 12, color: C.error, fontWeight: '600' },

  // Skills
  skillItem: {
    backgroundColor: C.surface, borderRadius: 12, padding: 12, marginBottom: 8,
    borderWidth: 1, borderColor: C.outlineVariant,
  },
  skillInfo: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  skillEmoji: { fontSize: 24 },
  skillText: { flex: 1 },
  skillName: { fontSize: 15, fontWeight: '600', color: C.onSurface },
  skillDesc: { fontSize: 12, color: C.onSurfaceVariant, marginTop: 2 },
  skillMeta: { fontSize: 11, color: C.onSurfaceVariant, marginTop: 2, opacity: 0.7 },

  // Cron
  cronItem: {
    backgroundColor: C.surface, borderRadius: 12, padding: 12, marginBottom: 8,
    borderWidth: 1, borderColor: C.outlineVariant,
  },
  cronInfo: { marginBottom: 6 },
  cronName: { fontSize: 15, fontWeight: '600', color: C.onSurface },
  cronSchedule: { fontSize: 12, color: C.primary, marginTop: 2, fontWeight: '500' },
  cronPrompt: { fontSize: 12, color: C.onSurfaceVariant, marginTop: 4 },
  cronMeta: { fontSize: 11, color: C.onSurfaceVariant, marginTop: 4, opacity: 0.7 },
  cronActions: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  cronBtn: { paddingHorizontal: 12, paddingVertical: 4, borderRadius: 8 },
  cronBtnPause: { backgroundColor: '#FFF3E0' },
  cronBtnResume: { backgroundColor: '#E8F5E9' },
  cronBtnText: { fontSize: 12, fontWeight: '600' },

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

  // Toggle
  toggleRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  toggleLabel: { fontSize: 15, fontWeight: '500', color: C.onSurface },
  toggleDesc: { fontSize: 12, color: C.onSurfaceVariant, marginTop: 2 },
  toggleIndicator: {
    paddingHorizontal: 12, paddingVertical: 6, borderRadius: 16,
    backgroundColor: C.surfaceVariant,
  },
  toggleOn: { backgroundColor: C.primaryContainer },
  toggleText: { fontSize: 13, fontWeight: '600', color: C.onSurfaceVariant },

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
