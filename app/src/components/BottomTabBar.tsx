import React from 'react'
import { Pressable, View, Text, StyleSheet } from 'react-native'
import { usePathname, useRouter } from 'expo-router'
import { useApp } from '../context/AppContext'
import { Home, Briefcase, Heart, Coffee } from './icons'

export default function BottomTabBar() {
  const { t } = useApp()
  const router = useRouter()
  const pathname = usePathname()

  const tabs = [
    {
      id: 'home',
      label: 'Home',
      icon: Home,
      screen: '/',
    },
    {
      id: 'work',
      label: 'Work',
      icon: Briefcase,
      screen: '/work',
    },
    {
      id: 'personal',
      label: 'Personal',
      icon: Heart,
      screen: '/personal',
    },
    {
      id: 'leisure',
      label: 'Leisure',
      icon: Coffee,
      screen: '/leisure',
    },
  ]

  return (
    <View
      style={[
        styles.container,
        {
          backgroundColor: t.surface,
          borderTopColor: t.border,
        },
      ]}
    >
      {tabs.map(tab => {
        const active = pathname === tab.screen

        const Icon = tab.icon

        return (
          <Pressable
            key={tab.id}
            onPress={() => router.push(tab.screen as any)}
            style={({ pressed }) => [
              styles.tab,
              pressed && styles.pressed,
            ]}
          >
            <Icon
              size={22}
              color={active ? t.primary : t.muted}
            />

            <Text
              style={[
                styles.label,
                {
                  color: active ? t.primary : t.muted,
                  fontWeight: active ? '600' : '400',
                },
              ]}
            >
              {tab.label}
            </Text>
          </Pressable>
        )
      })}
    </View>
  )
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-around',
    paddingHorizontal: 8,
    paddingTop: 8,
    paddingBottom: 24,
    borderTopWidth: 1,
  },

  tab: {
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
    paddingHorizontal: 20,
    paddingVertical: 4,
    borderRadius: 12,
  },

  label: {
    fontSize: 11,
    fontFamily: 'Outfit',
  },

  pressed: {
    opacity: 0.7,
  },
})