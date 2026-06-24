import React, { useEffect, useState } from 'react';
import { View, Text, FlatList, TouchableOpacity, Switch, StyleSheet } from 'react-native';
import { skillsApi } from '../../api/features';
import { colors } from '../../theme/colors';
import { spacing, radius } from '../../theme/spacing';
import { typography } from '../../theme/typography';
import type { Skill } from '../../api/types';

export function SkillsScreen() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(false);

  const loadSkills = async () => {
    setLoading(true);
    try {
      const data = await skillsApi.list();
      setSkills(data);
    } catch (e) {
      console.error('Failed to load skills', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSkills();
  }, []);

  const toggleSkill = async (name: string, enabled: boolean) => {
    try {
      await skillsApi.toggle(name, !enabled);
      setSkills((prev) =>
        prev.map((s) => (s.name === name ? { ...s, enabled: !enabled } : s))
      );
    } catch (e) {
      console.error('Failed to toggle skill', e);
    }
  };

  const renderItem = ({ item }: { item: Skill }) => (
    <View style={styles.skillRow}>
      <View style={styles.skillInfo}>
        <Text style={styles.skillName}>{item.name}</Text>
        <Text style={styles.skillDesc} numberOfLines={2}>
          {item.description}
        </Text>
      </View>
      <Switch
        value={item.enabled}
        onValueChange={() => toggleSkill(item.name, item.enabled)}
        trackColor={{ false: colors.light.outline, true: colors.light.primary }}
        thumbColor={colors.light.onPrimary}
      />
    </View>
  );

  return (
    <View style={styles.container}>
      <FlatList
        data={skills}
        renderItem={renderItem}
        keyExtractor={(item) => item.name}
        contentContainerStyle={styles.list}
        refreshing={loading}
        onRefresh={loadSkills}
        ListEmptyComponent={
          <Text style={styles.emptyText}>No skills yet</Text>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.light.background },
  list: { padding: spacing.md },
  skillRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    backgroundColor: colors.light.surface,
    borderRadius: radius.lg,
    marginBottom: spacing.sm,
  },
  skillInfo: { flex: 1, marginRight: spacing.md },
  skillName: {
    ...typography.titleSmall,
    color: colors.light.onSurface,
  },
  skillDesc: {
    ...typography.bodySmall,
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
