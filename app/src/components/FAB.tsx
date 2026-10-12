import React, { useRef } from 'react'
import {
  Pressable,
  StyleSheet,
  Animated,
  PanResponder,
  Dimensions,
  Text,
  View,
} from 'react-native'
import { useRouter, usePathname } from 'expo-router'

import { useApp } from '../context/AppContext'
import { Plus, Sparkles } from './icons'

const { width, height } = Dimensions.get('window')

export default function FAB() {
  const { t } = useApp()
  const router = useRouter()
  const pathname = usePathname()

  const isDashboard = pathname === '/' || pathname === '/dashboard'

  const pan = useRef(new Animated.ValueXY()).current

  const panResponder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => false,

      onMoveShouldSetPanResponder: (_, gesture) => {
        return (
          Math.abs(gesture.dx) > 5 ||
          Math.abs(gesture.dy) > 5
        )
      },

      onPanResponderGrant: () => {
        pan.setOffset({
          x: (pan.x as any).__getValue(),
          y: (pan.y as any).__getValue(),
        })

        pan.setValue({
          x: 0,
          y: 0,
        })
      },

      onPanResponderMove: Animated.event(
        [
          null,
          {
            dx: pan.x,
            dy: pan.y,
          },
        ],
        { useNativeDriver: false }
      ),

      onPanResponderRelease: (_, gesture) => {
        pan.flattenOffset()

        const currentX = (pan.x as any).__getValue()
        const currentY = (pan.y as any).__getValue()

        const maxX = width - (isDashboard ? width - 40 : 76)
        const minX = -width + 76

        const clampedX = Math.max(
          minX,
          Math.min(maxX, currentX)
        )

        const maxY = height - 180
        const minY = -height + 180

        const clampedY = Math.max(
          minY,
          Math.min(maxY, currentY)
        )

        Animated.spring(pan, {
          toValue: {
            x: clampedX,
            y: clampedY,
          },
          useNativeDriver: false,
          tension: 80,
          friction: 8,
        }).start()
      },
    })
  ).current

  const openAgent = () => {
    router.push('/ChatScreen')
  }

  return (
    <Animated.View
      style={[
        styles.wrapper,
        isDashboard
          ? styles.dashboardWrapper
          : styles.defaultWrapper,
        {
          transform: pan.getTranslateTransform(),
        },
      ]}
      {...panResponder.panHandlers}
    >
      <Pressable
        onPress={openAgent}
        accessibilityRole="button"
        accessibilityLabel="Add a task or ask AI"
        style={({ pressed }) => [
          isDashboard
            ? styles.dashboardFab
            : styles.fab,
          {
            backgroundColor: t.primary,
            shadowColor: t.primary,
          },
          pressed && styles.pressed,
        ]}
      >
        {isDashboard ? (
          <View style={styles.dashboardContent}>
            <Sparkles
              size={17}
              color="#FFFFFF"
            />

            <Text style={styles.dashboardText}>
              Add a task or ask anything...
            </Text>
          </View>
        ) : (
          <View
                    style={[
                      styles.aiIcon,
                      {
                        backgroundColor: t.primary,
                      },
                    ]}
                  >
                    <Sparkles size={17} color="#FFFFFF" />
                  </View>
        )}
      </Pressable>
    </Animated.View>
  )
}

const styles = StyleSheet.create({
  wrapper: {
    position: 'absolute',
    zIndex: 100,
  },

  dashboardWrapper: {
    left: 20,
    right: 20,
    bottom: 90,
  },

  defaultWrapper: {
    right: 20,
    bottom: 90,
  },

  dashboardFab: {
    width: '100%',
    height: 48,
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',

    shadowOpacity: 0.33,
    shadowOffset: {
      width: 0,
      height: 4,
    },
    shadowRadius: 20,

    elevation: 8,
  },

  dashboardContent: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },

  dashboardText: {
    color: '#FFFFFF',
    fontSize: 13.5,
    fontWeight: '500',
  },
  aiIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
  },

  fab: {
    width: 56,
    height: 56,
    borderRadius: 999,
    alignItems: 'center',
    justifyContent: 'center',

    shadowOpacity: 0.33,
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