import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { MainTabs } from './MainTabs';
import { SplashScreen } from '../screens/onboarding/SplashScreen';
import { WelcomeScreen } from '../screens/onboarding/WelcomeScreen';
import { ProviderSetupScreen } from '../screens/onboarding/ProviderSetupScreen';
import { SkillDetailScreen } from '../screens/skills/SkillDetailScreen';
import { CronDetailScreen } from '../screens/cron/CronDetailScreen';
import { colors } from '../theme/colors';
import { useSettingsStore } from '../store';

export type RootStackParamList = {
  Splash: undefined;
  Welcome: undefined;
  ProviderSetup: undefined;
  Main: undefined;
  SkillDetail: { name: string };
  CronDetail: { id: string };
};

const Stack = createNativeStackNavigator<RootStackParamList>();

export function RootNavigator() {
  const { backendReady } = useSettingsStore();

  return (
    <NavigationContainer
      theme={{
        dark: false,
        colors: {
          primary: colors.light.primary,
          background: colors.light.background,
          card: colors.light.surface,
          text: colors.light.onSurface,
          border: colors.light.outline,
          notification: colors.light.error,
        },
        fonts: {
          regular: { fontFamily: '', fontWeight: '400' },
          medium: { fontFamily: '', fontWeight: '500' },
          bold: { fontFamily: '', fontWeight: '700' },
          heavy: { fontFamily: '', fontWeight: '900' },
        },
      }}
    >
      <Stack.Navigator
        screenOptions={{ headerShown: false }}
        initialRouteName={backendReady ? 'Main' : 'Splash'}
      >
        <Stack.Screen name="Splash" component={SplashScreen} />
        <Stack.Screen name="Welcome" component={WelcomeScreen} />
        <Stack.Screen name="ProviderSetup" component={ProviderSetupScreen} />
        <Stack.Screen name="Main" component={MainTabs} />
        <Stack.Screen
          name="SkillDetail"
          component={SkillDetailScreen}
          options={{ headerShown: true, title: 'Skill' }}
        />
        <Stack.Screen
          name="CronDetail"
          component={CronDetailScreen}
          options={{ headerShown: true, title: 'Scheduled Task' }}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
