import React from 'react'
import {
  Pressable,
  StyleSheet,
} from 'react-native'
import { useRouter } from 'expo-router'

import { useApp } from '../context/AppContext'
import { Plus } from './icons'

export default function FAB() {
  const { t } = useApp()
  const router = useRouter()

  return (
    <Pressable
      onPress={() => router.push('/add-task')}
      style={({ pressed }) => [
        styles.fab,
        {
          backgroundColor: t.primary,
          shadowColor: t.primary,
          shadowOpacity: 0.33,
        },
        pressed && styles.pressed,
      ]}
    >
      <Plus
        size={24}
        color="#FFFFFF"
      />
    </Pressable>
  )
}

const styles = StyleSheet.create({
  fab: {
    position: 'absolute',
    bottom: 24,
    right: 20,

    width: 56,
    height: 56,

    borderRadius: 999,

    alignItems: 'center',
    justifyContent: 'center',

    zIndex: 20,

    shadowOffset: {
      width: 0,
      height: 4,
    },

    shadowRadius: 20,

    elevation: 8,
  },

  pressed: {
    transform: [
      {
        scale: 0.95,
      },
    ],
  },
})

