import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { colors } from '../../theme/colors';
import { spacing } from '../../theme/spacing';
import { typography } from '../../theme/typography';

export function WelcomeScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.emoji}>🤖</Text>
      <Text style={styles.title}>Welcome to Hermes</Text>
      <Text style={styles.description}>
        Your self-improving AI agent that gets smarter the more you use it.
        Let's set up your first AI provider to get started.
      </Text>
      <TouchableOpacity style={styles.button}>
        <Text style={styles.buttonText}>Get Started</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.xl,
    backgroundColor: colors.light.background,
  },
  emoji: {
    fontSize: 64,
    marginBottom: spacing.lg,
  },
  title: {
    ...typography.headlineMedium,
    color: colors.light.onBackground,
    fontWeight: '700',
    textAlign: 'center',
  },
  description: {
    ...typography.bodyLarge,
    color: colors.light.onSurfaceVariant,
    textAlign: 'center',
    marginTop: spacing.md,
    marginBottom: spacing.xxl,
    lineHeight: 24,
  },
  button: {
    backgroundColor: colors.light.primary,
    paddingHorizontal: spacing.xxl,
    paddingVertical: spacing.md,
    borderRadius: 100,
  },
  buttonText: {
    ...typography.labelLarge,
    color: colors.light.onPrimary,
  },
});
