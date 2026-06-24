import React, { useEffect } from 'react';
import { View, Text, ActivityIndicator, StyleSheet } from 'react-native';
import { usePythonBackend } from '../../hooks/usePythonBackend';
import { colors } from '../../theme/colors';
import { spacing } from '../../theme/spacing';
import { typography } from '../../theme/typography';

export function SplashScreen() {
  const { backendReady, retry } = usePythonBackend();

  useEffect(() => {
    if (backendReady) {
      // Navigate to main - handled by RootNavigator
    }
  }, [backendReady]);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Hermes Agent</Text>
      <Text style={styles.subtitle}>Your self-improving AI companion</Text>
      <ActivityIndicator
        size="large"
        color={colors.light.primary}
        style={styles.loader}
      />
      <Text style={styles.status}>
        {backendReady ? 'Ready!' : 'Starting Python backend...'}
      </Text>
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
});
