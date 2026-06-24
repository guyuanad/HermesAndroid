import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { ChatScreen } from '../screens/chat/ChatScreen';
import { SessionListScreen } from '../screens/sessions/SessionListScreen';
import { SkillsScreen } from '../screens/skills/SkillsScreen';
import { SettingsScreen } from '../screens/settings/SettingsScreen';
import { colors } from '../theme/colors';

export type MainTabParamList = {
  Chat: undefined;
  Sessions: undefined;
  Skills: undefined;
  Settings: undefined;
};

const Tab = createBottomTabNavigator<MainTabParamList>();

export function MainTabs() {
  return (
    <Tab.Navigator
      screenOptions={{
        tabBarActiveTintColor: colors.light.primary,
        tabBarInactiveTintColor: colors.light.onSurfaceVariant,
        tabBarStyle: {
          backgroundColor: colors.light.surface,
          borderTopColor: colors.light.outlineVariant,
        },
        headerStyle: {
          backgroundColor: colors.light.surface,
        },
        headerTintColor: colors.light.onSurface,
      }}
    >
      <Tab.Screen
        name="Chat"
        component={ChatScreen}
        options={{
          tabBarLabel: 'Chat',
          title: 'Hermes',
        }}
      />
      <Tab.Screen
        name="Sessions"
        component={SessionListScreen}
        options={{
          tabBarLabel: 'Sessions',
          title: 'Sessions',
        }}
      />
      <Tab.Screen
        name="Skills"
        component={SkillsScreen}
        options={{
          tabBarLabel: 'Skills',
          title: 'Skills',
        }}
      />
      <Tab.Screen
        name="Settings"
        component={SettingsScreen}
        options={{
          tabBarLabel: 'Settings',
          title: 'Settings',
        }}
      />
    </Tab.Navigator>
  );
}
