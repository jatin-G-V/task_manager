import React from 'react'
import {
  Pressable,
  View,
  Text,
  StyleSheet,
} from 'react-native'

import { useApp } from '../context/AppContext'
import type { Task } from '../types'

import {
  AlertTriangle,
  Link2,
  Clock,
} from './icons'

interface Props {
  task: Task
  variant?: 'work' | 'personal' | 'leisure'
  onTap?: () => void
}

const priorityDot: Record<string, string> = {
  high: '#E9713C',
  medium: '#F5C842',
  low: '#3DAF72',
}
function formatDeadline(iso: string): string {
  if (!iso) return 'No deadline set'
  const date = new Date(iso)
  const hasTime = date.getHours() !== 0 || date.getMinutes() !== 0
  const dateStr = date.toLocaleDateString()
  if (!hasTime) return dateStr
  const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  return `${dateStr} · ${timeStr}`
}
export default function TaskCard({
  task,
  variant,
  onTap,
}: Props) {
  const { t } = useApp()

  const section =
    variant ?? task.section

  const handleTap = () => {
    if (onTap) {
      onTap()
    }
  }

  return (
    <Pressable
      onPress={handleTap}
      style={({ pressed }) => [
        styles.card,
        {
          backgroundColor: t.surface,
          borderColor: t.border,
        },
        pressed && styles.pressed,
      ]}
    >
      <View style={styles.topRow}>
        <View style={styles.content}>
          {/* Title */}
          <View style={styles.titleRow}>
            <View
              style={[
                styles.priorityDot,
                {
                  backgroundColor:
                    priorityDot[task.priority],
                },
              ]}
            />

            <Text
              numberOfLines={1}
              ellipsizeMode="tail"
              style={[
                styles.title,
                {
                  fontSize:
                    section === 'leisure'
                      ? 14
                      : 15,
                  color: t.text,
                },
              ]}
            >
              {task.title}
            </Text>
          </View>

          {/* Meta information */}
          <View style={styles.metaRow}>
            {/* Deadline */}
            <View style={styles.metaItem}>
              <Clock
                size={12}
                color={
                  task.atRisk
                    ? t.risk
                    : t.muted
                }
              />

              <Text
                style={[
                  styles.deadline,
                  {
                    color: task.atRisk
                      ? t.risk
                      : t.muted,
                    fontWeight:
                      task.atRisk
                        ? '500'
                        : '400',
                  },
                ]}
              >
                {formatDeadline(task.deadline)}
              </Text>
            </View>

            {/* At risk */}
            {task.atRisk && (
              <View
                style={[
                  styles.badge,
                  {
                    backgroundColor:
                      t.riskBg,
                  },
                ]}
              >
                <AlertTriangle
                  size={11}
                  color={t.risk}
                />

                <Text
                  style={[
                    styles.badgeText,
                    {
                      color: t.risk,
                      fontWeight: '500',
                    },
                  ]}
                >
                  at risk
                </Text>
              </View>
            )}

            {/* Blocked */}
            {task.blocked && (
              <View
                style={[
                  styles.badge,
                  {
                    backgroundColor:
                      t.surface2,
                  },
                ]}
              >
                <Link2
                  size={11}
                  color={t.muted}
                />

                <Text
                  style={[
                    styles.badgeText,
                    {
                      color: t.muted,
                      fontWeight: '400',
                    },
                  ]}
                >
                  blocked
                </Text>
              </View>
            )}
          </View>
        </View>

        {/* Work priority score */}
        {section === 'work' &&
          task.priorityScore && (
            <View
              style={[
                styles.priorityScore,
                {
                  backgroundColor:
                    t.surface2,
                },
              ]}
            >
              <Text
                style={[
                  styles.priorityScoreText,
                  {
                    color: t.text,
                  },
                ]}
              >
                {task.priorityScore}
              </Text>
            </View>
          )}
      </View>
    </Pressable>
  )
}

const styles = StyleSheet.create({
  card: {
    width: '100%',
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
  },

  pressed: {
    transform: [
      {
        scale: 0.98,
      },
    ],
  },

  topRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
  },

  content: {
    flex: 1,
    minWidth: 0,
  },

  titleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 6,
  },

  priorityDot: {
    width: 7,
    height: 7,
    borderRadius: 999,
    marginRight: 8,
    flexShrink: 0,
  },

  title: {
    flex: 1,
    fontWeight: '500',
    fontFamily: 'Outfit',
  },

  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },

  metaItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },

  deadline: {
    fontSize: 12,
    fontFamily: 'Outfit',
  },

  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 999,
  },

  badgeText: {
    fontSize: 11,
    fontFamily: 'Outfit',
  },

  priorityScore: {
    width: 36,
    height: 36,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: 12,
    flexShrink: 0,
  },

  priorityScoreText: {
    fontSize: 13,
    fontWeight: '600',
    fontFamily: 'Outfit',
  },
})
