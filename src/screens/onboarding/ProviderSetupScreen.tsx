import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
} from 'react-native';
import { colors } from '../../theme/colors';
import { spacing } from '../../theme/spacing';
import { typography } from '../../theme/typography';
import { radius } from '../../theme/spacing';

const PROVIDERS = [
  { key: 'openrouter', label: 'OpenRouter', placeholder: 'sk-or-...' },
  { key: 'anthropic', label: 'Anthropic', placeholder: 'sk-ant-...' },
  { key: 'google', label: 'Google Gemini', placeholder: 'AI...' },
  { key: 'openai', label: 'OpenAI', placeholder: 'sk-...' },
  { key: 'glm', label: 'z.ai / GLM', placeholder: '...' },
  { key: 'kimi', label: 'Kimi / Moonshot', placeholder: '...' },
];

export function ProviderSetupScreen() {
  const [selectedProvider, setSelectedProvider] = useState('openrouter');
  const [apiKey, setApiKey] = useState('');

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Configure AI Provider</Text>
      <Text style={styles.subtitle}>
        Choose a provider and enter your API key. You can add more later.
      </Text>

      <View style={styles.providerList}>
        {PROVIDERS.map((p) => (
          <TouchableOpacity
            key={p.key}
            style={[
              styles.providerItem,
              selectedProvider === p.key && styles.providerItemSelected,
            ]}
            onPress={() => setSelectedProvider(p.key)}
          >
            <Text
              style={[
                styles.providerLabel,
                selectedProvider === p.key && styles.providerLabelSelected,
              ]}
            >
              {p.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <TextInput
        style={styles.input}
        placeholder={
          PROVIDERS.find((p) => p.key === selectedProvider)?.placeholder
        }
        placeholderTextColor={colors.light.onSurfaceVariant}
        value={apiKey}
        onChangeText={setApiKey}
        secureTextEntry
        autoCapitalize="none"
        autoCorrect={false}
      />

      <TouchableOpacity
        style={[styles.button, !apiKey.trim() && styles.buttonDisabled]}
        disabled={!apiKey.trim()}
      >
        <Text style={styles.buttonText}>Continue</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.light.background,
  },
  content: {
    padding: spacing.xl,
  },
  title: {
    ...typography.headlineSmall,
    color: colors.light.onBackground,
    fontWeight: '700',
  },
  subtitle: {
    ...typography.bodyMedium,
    color: colors.light.onSurfaceVariant,
    marginTop: spacing.sm,
    marginBottom: spacing.xl,
  },
  providerList: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
    marginBottom: spacing.xl,
  },
  providerItem: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.light.outline,
    backgroundColor: colors.light.surface,
  },
  providerItemSelected: {
    borderColor: colors.light.primary,
    backgroundColor: colors.light.primaryContainer,
  },
  providerLabel: {
    ...typography.labelMedium,
    color: colors.light.onSurface,
  },
  providerLabelSelected: {
    color: colors.light.onPrimaryContainer,
  },
  input: {
    ...typography.bodyLarge,
    borderWidth: 1,
    borderColor: colors.light.outline,
    borderRadius: radius.lg,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    color: colors.light.onSurface,
    marginBottom: spacing.xl,
  },
  button: {
    backgroundColor: colors.light.primary,
    paddingVertical: spacing.md,
    borderRadius: 100,
    alignItems: 'center',
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  buttonText: {
    ...typography.labelLarge,
    color: colors.light.onPrimary,
  },
});
