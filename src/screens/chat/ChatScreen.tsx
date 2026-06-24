import React, { useCallback, useRef, useState } from 'react';
import {
  View,
  Text,
  TextInput,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { useChat } from '../../hooks/useChat';
import { colors } from '../../theme/colors';
import { spacing, radius } from '../../theme/spacing';
import { typography } from '../../theme/typography';
import type { Message } from '../../api/types';

export function ChatScreen() {
  const { messages, isStreaming, sendMessage, newSession, stopStreaming } =
    useChat();
  const [inputText, setInputText] = useState('');
  const flatListRef = useRef<FlatList>(null);

  const handleSend = useCallback(() => {
    if (inputText.trim()) {
      sendMessage(inputText.trim());
      setInputText('');
    }
  }, [inputText, sendMessage]);

  const renderMessage = useCallback(({ item }: { item: Message }) => {
    const isUser = item.role === 'user';
    const isTool = item.role === 'tool';

    if (isTool) {
      return (
        <View style={styles.toolMessage}>
          <Text style={styles.toolLabel}>Tool</Text>
          <Text style={styles.toolContent} numberOfLines={5}>
            {item.content}
          </Text>
        </View>
      );
    }

    return (
      <View style={[styles.messageBubble, isUser ? styles.userBubble : styles.assistantBubble]}>
        <Text style={[styles.messageText, isUser ? styles.userText : styles.assistantText]}>
          {item.content || (isStreaming && !isUser ? '...' : '')}
        </Text>
      </View>
    );
  }, [isStreaming]);

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'android' ? undefined : 'padding'}
    >
      <FlatList
        ref={flatListRef}
        data={messages}
        renderItem={renderMessage}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.messageList}
        onContentSizeChange={() => flatListRef.current?.scrollToEnd()}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyTitle}>Hermes Agent</Text>
            <Text style={styles.emptySubtitle}>Start a conversation</Text>
            <TouchableOpacity style={styles.newSessionButton} onPress={newSession}>
              <Text style={styles.newSessionButtonText}>New Session</Text>
            </TouchableOpacity>
          </View>
        }
      />

      <View style={styles.inputBar}>
        <TextInput
          style={styles.textInput}
          placeholder="Message Hermes..."
          placeholderTextColor={colors.light.onSurfaceVariant}
          value={inputText}
          onChangeText={setInputText}
          multiline
          editable={!isStreaming}
        />
        <TouchableOpacity
          style={[styles.sendButton, !inputText.trim() && styles.sendButtonDisabled]}
          onPress={handleSend}
          disabled={!inputText.trim() || isStreaming}
        >
          <Text style={styles.sendButtonText}>↑</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.light.background },
  messageList: { padding: spacing.md, paddingBottom: spacing.xl },
  messageBubble: {
    maxWidth: '80%',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    borderRadius: radius.xl,
    marginBottom: spacing.sm,
  },
  userBubble: {
    alignSelf: 'flex-end',
    backgroundColor: colors.light.primary,
  },
  assistantBubble: {
    alignSelf: 'flex-start',
    backgroundColor: colors.light.surfaceVariant,
  },
  userText: { color: colors.light.onPrimary, ...typography.bodyMedium },
  assistantText: { color: colors.light.onSurfaceVariant, ...typography.bodyMedium },
  messageText: {},
  toolMessage: {
    alignSelf: 'flex-start',
    backgroundColor: colors.light.tertiaryContainer,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    marginBottom: spacing.sm,
    maxWidth: '90%',
  },
  toolLabel: {
    ...typography.labelSmall,
    color: colors.light.onTertiaryContainer,
    fontWeight: '700',
    marginBottom: 2,
  },
  toolContent: {
    ...typography.bodySmall,
    color: colors.light.onTertiaryContainer,
  },
  inputBar: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.light.outlineVariant,
    backgroundColor: colors.light.surface,
  },
  textInput: {
    flex: 1,
    ...typography.bodyMedium,
    color: colors.light.onSurface,
    maxHeight: 120,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.light.surfaceVariant,
    borderRadius: radius.xxl,
  },
  sendButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.light.primary,
    justifyContent: 'center',
    alignItems: 'center',
    marginLeft: spacing.sm,
  },
  sendButtonDisabled: { opacity: 0.4 },
  sendButtonText: {
    color: colors.light.onPrimary,
    fontSize: 20,
    fontWeight: '700',
  },
  emptyContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingTop: 100,
  },
  emptyTitle: {
    ...typography.headlineMedium,
    color: colors.light.onBackground,
    fontWeight: '700',
  },
  emptySubtitle: {
    ...typography.bodyLarge,
    color: colors.light.onSurfaceVariant,
    marginTop: spacing.sm,
  },
  newSessionButton: {
    marginTop: spacing.xl,
    backgroundColor: colors.light.primary,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.md,
    borderRadius: 100,
  },
  newSessionButtonText: {
    ...typography.labelLarge,
    color: colors.light.onPrimary,
  },
});
