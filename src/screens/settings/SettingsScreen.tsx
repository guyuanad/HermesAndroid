import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  Switch,
  TextInput,
  Alert,
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
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [keyValue, setKeyValue] = useState('');

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

  const handleSetApiKey = async (key: string) => {
    if (!keyValue.trim()) {
      Alert.alert('Error', 'Please enter a value');
      return;
    }
    try {
      await envApi.set(key, keyValue.trim());
      setEditingKey(null);
      setKeyValue('');
      loadData();
      Alert.alert('Success', `${key} saved`);
    } catch (e) {
      Alert.alert('Error', 'Failed to save API key');
    }
  };

  const handleDeleteApiKey = async (key: string) => {
    try {
      await envApi.delete(key);
      loadData();
    } catch (e) {
      Alert.alert('Error', 'Failed to delete API key');
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
      </View>

      {/* API Keys Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>API Keys</Text>
        {envVars.map((env) => (
          <View key={env.key} style={styles.envRow}>
            <View style={styles.envInfo}>
              <Text style={styles.envKey}>{env.key}</Text>
              <Text style={styles.envValue}>
                {env.is_set ? env.value : 'Not set'}
              </Text>
            </View>
            <View style={styles.envActions}>
              <TouchableOpacity
                style={styles.envButton}
                onPress={() => {
                  setEditingKey(env.key);
                  setKeyValue('');
                }}
              >
                <Text style={styles.envButtonText}>
                  {env.is_set ? 'Edit' : 'Set'}
                </Text>
              </TouchableOpacity>
              {env.is_set && (
                <TouchableOpacity
                  style={[styles.envButton, styles.envButtonDanger]}
                  onPress={() => handleDeleteApiKey(env.key)}
                >
                  <Text style={styles.envButtonText}>Delete</Text>
                </TouchableOpacity>
              )}
            </View>
            {editingKey === env.key && (
              <View style={styles.keyInputRow}>
                <TextInput
                  style={styles.keyInput}
                  placeholder={`Enter ${env.key}`}
                  placeholderTextColor={colors.light.onSurfaceVariant}
                  value={keyValue}
                  onChangeText={setKeyValue}
                  secureTextEntry
                  autoCapitalize="none"
                />
                <TouchableOpacity
                  style={styles.saveButton}
                  onPress={() => handleSetApiKey(env.key)}
                >
                  <Text style={styles.saveButtonText}>Save</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.cancelButton}
                  onPress={() => setEditingKey(null)}
                >
                  <Text style={styles.cancelButtonText}>Cancel</Text>
                </TouchableOpacity>
              </View>
            )}
          </View>
        ))}
      </View>

      {/* About Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>About</Text>
        <View style={styles.row}>
          <Text style={styles.rowLabel}>Version</Text>
          <Text style={styles.rowValue}>0.1.0-android</Text>
        </View>
        <View style={styles.row}>
          <Text style={styles.rowLabel}>Backend</Text>
          <Text style={styles.rowValue}>FastAPI + OpenAI SDK</Text>
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
  envRow: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.light.outlineVariant,
    paddingVertical: spacing.sm,
  },
  envInfo: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  envKey: {
    ...typography.bodyMedium,
    color: colors.light.onSurface,
    fontWeight: '600',
  },
  envValue: {
    ...typography.bodySmall,
    color: colors.light.onSurfaceVariant,
  },
  envActions: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
  envButton: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: radius.md,
    backgroundColor: colors.light.primary,
  },
  envButtonDanger: {
    backgroundColor: colors.light.error,
  },
  envButtonText: {
    ...typography.labelSmall,
    color: colors.light.onPrimary,
  },
  keyInputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: spacing.sm,
    gap: spacing.sm,
  },
  keyInput: {
    flex: 1,
    ...typography.bodyMedium,
    color: colors.light.onSurface,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.light.surfaceVariant,
    borderRadius: radius.md,
  },
  saveButton: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    backgroundColor: colors.light.primary,
  },
  saveButtonText: {
    ...typography.labelSmall,
    color: colors.light.onPrimary,
    fontWeight: '700',
  },
  cancelButton: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  cancelButtonText: {
    ...typography.labelSmall,
    color: colors.light.onSurfaceVariant,
  },
});
