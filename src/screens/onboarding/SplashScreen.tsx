import React, { useEffect } from 'react';
import { View, Text, ActivityIndicator, StyleSheet, TouchableOpacity } from 'react';
import { usePythonBackend } from '../../hooks/usePythonBackend';
import { colors } from '../../theme/colors';
import { spacing } from '../../theme/spacing';
import { typography } from '../../theme/typography';

export function SplashScreen() {
  const { backendReady, retry } = usePythonBackend();

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Hermes Agent</Text>
      <Text style={styles.subtitle}>Your self-improving AI companion</Text>
      <ActivityIndicator
        size="large"
        color={colors.light.onPrimary}
        style={styles.loader}
      />
      <Text style={styles.status}>
        {backendReady ? 'Ready!' : 'Starting Python backend...'}
      </Text>
      {!backendReady && (
        <TouchableOpacity style={styles.retryButton} onPress={retry}>
          <Text style={styles.retryText}>Retry</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.light.primary,
  },
  title: {
    ...typography.headlineLarge,
    color: colors.light.onPrimary,
    fontWeight: '700',
  },
  subtitle: {
    ...typography.bodyLarge,
    color: colors.light.onPrimary,
    opacity: 0.8,
    marginTop: spacing.sm,
  },
  loader: {
    marginTop: spacing.xxl,
  },
  status: {
    ...typography.bodySmall,
    color: colors.light.onPrimary,
    opacity: 0.6,
    marginTop: spacing.md,
  },
  retryButton: {
    marginTop: spacing.lg,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.sm,
    borderRadius: 100,
    backgroundColor: 'rgba(255,255,255,0.2)',
  },
  retryText: {
    ...typography.labelLarge,
    color: colors.light.onPrimary,
  },
});
