import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  Switch,
  StyleSheet,
} from 'react-native';
import { configApi, envApi, modelApi, systemApi } from '../../api/config';
import { colors } from '../../theme/colors';
import { spacing, radius } from '../../theme/spacing';
import { typography } from '../../theme/typography';
import type { HermesConfig, ModelOption, EnvVar } from '../../api/types';

export function SettingsScreen() {
  const [config, setConfig] = useState<HermesConfig | null>(null);
  const [models, setModels] = useState<ModelOption[]>([]);
  const [envVars, setEnvVars] = useState<EnvVar[]>([]);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [cfg, modelList, envs] = await Promise.all([
        configApi.get(),
        modelApi.options().catch(() => []),
        envApi.get().catch(() => []),
      ]);
      setConfig(cfg);
      setModels(modelList);
      setEnvVars(envs);
    } catch (e) {
      console.error('Failed to load settings', e);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Model Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Model</Text>
        <View style={styles.row}>
          <Text style={styles.rowLabel}>Default Model</Text>
          <Text style={styles.rowValue}>
            {config?.model.default || 'Not set'}
          </Text>
        </View>
        <View style={styles.row}>
          <Text style={styles.rowLabel}>Provider</Text>
          <Text style={styles.rowValue}>
            {config?.model.provider || 'auto'}
          </Text>
        </View>
        <View style={styles.row}>
          <Text style={styles.rowLabel}>Reasoning Effort</Text>
          <Text style={styles.rowValue}>
            {config?.agent.reasoning_effort || 'medium'}
          </Text>
        </View>
      </View>

      {/* Memory Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Memory</Text>
        <View style={styles.row}>
          <Text style={styles.rowLabel}>Agent Memory</Text>
          <Switch
            value={config?.memory.memory_enabled ?? true}
            trackColor={{ false: colors.light.outline, true: colors.light.primary }}
            thumbColor={colors.light.onPrimary}
          />
        </View>
        <View style={styles.row}>
          <Text style={styles.rowLabel}>User Profile</Text>
          <Switch
            value={config?.memory.user_profile_enabled ?? true}
            trackColor={{ false: colors.light.outline, true: colors.light.primary }}
            thumbColor={colors.light.onPrimary}
          />
        </View>
      </View>

      {/* Compression Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Context</Text>
        <View style={styles.row}>
          <Text style={styles.rowLabel}>Auto Compression</Text>
          <Switch
            value={config?.compression.enabled ?? true}
            trackColor={{ false: colors.light.outline, true: colors.light.primary }}
            thumbColor={colors.light.onPrimary}
          />
        </View>
      </View>

      {/* API Keys Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>API Keys</Text>
        {envVars.map((env) => (
          <View key={env.key} style={styles.row}>
            <Text style={styles.rowLabel}>{env.key}</Text>
            <Text style={styles.rowValue}>
              {env.is_set ? '••••••••' : 'Not set'}
            </Text>
          </View>
        ))}
        {envVars.length === 0 && (
          <Text style={styles.emptyText}>No API keys configured</Text>
        )}
      </View>

      {/* About Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>About</Text>
        <View style={styles.row}>
          <Text style={styles.rowLabel}>Version</Text>
          <Text style={styles.rowValue}>1.0.0</Text>
        </View>
        <View style={styles.row}>
          <Text style={styles.rowLabel}>Backend</Text>
          <Text style={styles.rowValue}>hermes-agent 0.17.0</Text>
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.light.background },
  content: { padding: spacing.md, paddingBottom: spacing.xxxl },
  section: {
    backgroundColor: colors.light.surface,
    borderRadius: radius.lg,
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  sectionTitle: {
    ...typography.titleMedium,
    color: colors.light.primary,
    marginBottom: spacing.md,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.light.outlineVariant,
  },
  rowLabel: {
    ...typography.bodyMedium,
    color: colors.light.onSurface,
  },
  rowValue: {
    ...typography.bodyMedium,
    color: colors.light.onSurfaceVariant,
  },
  emptyText: {
    ...typography.bodySmall,
    color: colors.light.onSurfaceVariant,
    textAlign: 'center',
    paddingVertical: spacing.md,
  },
});
