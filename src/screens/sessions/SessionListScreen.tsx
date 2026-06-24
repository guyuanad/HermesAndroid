import React, { useCallback, useEffect, useState } from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  TextInput,
  StyleSheet,
  Alert,
} from 'react-native';
import { sessionsApi } from '../../api/sessions';
import { colors } from '../../theme/colors';
import { spacing, radius } from '../../theme/spacing';
import { typography } from '../../theme/typography';
import type { Session } from '../../api/types';

export function SessionListScreen() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);

  const loadSessions = useCallback(async () => {
    setLoading(true);
    try {
      const data = await sessionsApi.list();
      setSessions(data);
    } catch (e) {
      console.error('Failed to load sessions', e);
    } finally {
      setLoading(false);
    }
  }, []);

  const searchSessions = useCallback(async (query: string) => {
    if (!query.trim()) {
      loadSessions();
      return;
    }
    try {
      const data = await sessionsApi.search(query);
      setSessions(data);
    } catch (e) {
      console.error('Search failed', e);
    }
  }, [loadSessions]);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const deleteSession = useCallback(
    (id: string) => {
      Alert.alert('Delete Session', 'Are you sure?', [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            await sessionsApi.delete(id);
            loadSessions();
          },
        },
      ]);
    },
    [loadSessions]
  );

  const renderItem = useCallback(
    ({ item }: { item: Session }) => (
      <TouchableOpacity style={styles.sessionRow}>
        <View style={styles.sessionInfo}>
          <Text style={styles.sessionTitle} numberOfLines={1}>
            {item.title || 'New Session'}
          </Text>
          <Text style={styles.sessionPreview} numberOfLines={2}>
            {item.preview || 'No messages yet'}
          </Text>
        </View>
        <View style={styles.sessionMeta}>
          <Text style={styles.sessionModel}>{item.model}</Text>
          <Text style={styles.sessionTime}>
            {new Date(item.updated_at).toLocaleDateString()}
          </Text>
        </View>
      </TouchableOpacity>
    ),
    []
  );

  return (
    <View style={styles.container}>
      <TextInput
        style={styles.searchInput}
        placeholder="Search sessions..."
        placeholderTextColor={colors.light.onSurfaceVariant}
        value={searchQuery}
        onChangeText={(text) => {
          setSearchQuery(text);
          searchSessions(text);
        }}
      />
      <FlatList
        data={sessions}
        renderItem={renderItem}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.list}
        refreshing={loading}
        onRefresh={loadSessions}
        ListEmptyComponent={
          <Text style={styles.emptyText}>No sessions yet</Text>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.light.background },
  searchInput: {
    ...typography.bodyMedium,
    margin: spacing.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    backgroundColor: colors.light.surfaceVariant,
    borderRadius: radius.xxl,
    color: colors.light.onSurface,
  },
  list: { paddingHorizontal: spacing.md },
  sessionRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    backgroundColor: colors.light.surface,
    borderRadius: radius.lg,
    marginBottom: spacing.sm,
  },
  sessionInfo: { flex: 1, marginRight: spacing.md },
  sessionTitle: {
    ...typography.titleSmall,
    color: colors.light.onSurface,
  },
  sessionPreview: {
    ...typography.bodySmall,
    color: colors.light.onSurfaceVariant,
    marginTop: 2,
  },
  sessionMeta: { alignItems: 'flex-end' },
  sessionModel: {
    ...typography.labelSmall,
    color: colors.light.primary,
  },
  sessionTime: {
    ...typography.labelSmall,
    color: colors.light.onSurfaceVariant,
    marginTop: 2,
  },
  emptyText: {
    ...typography.bodyLarge,
    color: colors.light.onSurfaceVariant,
    textAlign: 'center',
    marginTop: 40,
  },
});
