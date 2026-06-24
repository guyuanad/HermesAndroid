import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { colors } from '../../theme/colors';
import { spacing } from '../../theme/spacing';
import { typography } from '../../theme/typography';

export function CronDetailScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Scheduled Task</Text>
      <Text style={styles.subtitle}>Coming soon</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.light.background, padding: spacing.xl },
  title: { ...typography.headlineSmall, color: colors.light.onBackground },
  subtitle: { ...typography.bodyMedium, color: colors.light.onSurfaceVariant, marginTop: spacing.sm },
});
