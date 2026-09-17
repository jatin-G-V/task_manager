import React, { useRef } from 'react'
import {
  Pressable,
  StyleSheet,
  Animated,
  PanResponder,
  Dimensions,
} from 'react-native'
import { useRouter } from 'expo-router'

import { useApp } from '../context/AppContext'
import { Plus } from './icons'

const { width, height } = Dimensions.get('window')

export default function FAB() {
  const { t } = useApp()
  const router = useRouter()

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

        const maxX = width - 76
        const minX = -width + 76

        // Keep button reasonably inside screen
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

  return (
    <Animated.View
      style={[
        styles.wrapper,
        {
          transform: pan.getTranslateTransform(),
        },
      ]}
      {...panResponder.panHandlers}
    >
      <Pressable
        onPress={() => router.push('/add-task')}
        style={({ pressed }) => [
          styles.fab,
          {
            backgroundColor: t.primary,
            shadowColor: t.primary,
          },
          pressed && styles.pressed,
        ]}
      >
        <Plus
          size={24}
          color="#FFFFFF"
        />
      </Pressable>
    </Animated.View>
  )
}

const styles = StyleSheet.create({
  wrapper: {
    position: 'absolute',
    right: 20,
    bottom: 90,
    zIndex: 100,
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