import React, { useState } from 'react'
import type { Task } from '../types'
import DateTimePicker from '@react-native-community/datetimepicker'
import { Alert, Platform } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'

import {
  View,
  Text,
  ScrollView,
  Pressable,
  TextInput,
  StyleSheet,
} from 'react-native'

import { useLocalSearchParams, useRouter } from 'expo-router'

import { useApp } from '../context/AppContext'

import {
  ChevronLeft,
  Check,
  AlertTriangle,
  Calendar,
  Clock,
  Pencil,
  Sparkles,
} from '../components/icons'

const priorityColors: Record<string, string> = {
  high: '#E9713C',
  medium: '#F5C842',
  low: '#3DAF72',
}

export default function TaskDetailScreen() {
  const { id, section } = useLocalSearchParams<{
    id: string
    section: 'work' | 'personal' | 'leisure'
  }>()

  const router = useRouter()

  const {
    tasks,
    t,
    completeTask,
    updateTask,
  } = useApp()

  const task = tasks[section].find(
    item => item.id === id
  )

  const [steps, setSteps] = useState(
    task?.steps?.map(s => ({
      text: s,
      done: false,
    })) ?? []
  )

  /*
   * --------------------------------------------------
   * DEADLINE STATE
   * --------------------------------------------------
   */

  const initialDeadline =
    task?.deadline &&
    task.deadline !== 'No deadline set'
      ? new Date(task.deadline)
      : null

  const [deadlineDate, setDeadlineDate] =
    useState<Date | null>(
      initialDeadline &&
      !isNaN(initialDeadline.getTime())
        ? initialDeadline
        : null
    )

  const [hasTime, setHasTime] = useState(
    !!(
      initialDeadline &&
      !isNaN(initialDeadline.getTime()) &&
      (
        initialDeadline.getHours() !== 0 ||
        initialDeadline.getMinutes() !== 0
      )
    )
  )

  const [showDatePicker, setShowDatePicker] =
    useState(false)

  const [showTimePicker, setShowTimePicker] =
    useState(false)

  const showAlert = (
  title: string,
  message: string
) => {
  if (Platform.OS === 'web') {
    window.alert(`${title}: ${message}`)
  } else {
    Alert.alert(title, message)
  }
}  

  const saveDeadline = async (date: Date) => {
    if (!task) return

    try {
      await updateTask(
        task.id,
        section,
        {
          deadline: date.toISOString(),
        }
      )
    } catch (e) {
      console.error(
        'Failed to save deadline:',
        e
      )
    }
  }

 const onDateChange = (event: any, selected?: Date) => {
  if (Platform.OS !== 'ios') {
    setShowDatePicker(false)
  }

  if (event.type === 'dismissed' || !selected) return

  const merged = new Date(selected)

  if (deadlineDate && hasTime) {
    merged.setHours(deadlineDate.getHours(), deadlineDate.getMinutes(), 0, 0)
  } else {
    merged.setHours(23, 59, 0, 0)
  }

  const now = new Date()
  if (merged < now) {
    showAlert('Invalid deadline', "You can't set a deadline in the past.")
    return
  }

  setDeadlineDate(merged)
  saveDeadline(merged)
}

const onTimeChange = (
  event: any,
  selected?: Date
) => {
  setShowTimePicker(false)

  if (
    event.type === 'dismissed' ||
    !selected ||
    !deadlineDate
  ) {
    return
  }

  const merged = new Date(
    deadlineDate
  )

  merged.setHours(
    selected.getHours(),
    selected.getMinutes(),
    0,
    0
  )

  const now = new Date()

  if (merged < now) {
    showAlert(
      'Invalid deadline',
      "You can't set a deadline time in the past."
    )
    return
  }

  setDeadlineDate(merged)
  setHasTime(true)

  saveDeadline(merged)
}

  /*
   * --------------------------------------------------
   * OTHER STATE
   * --------------------------------------------------
   */

  const [title, setTitle] = useState(
    task?.title ?? ''
  )

  const [editingTitle, setEditingTitle] =
    useState(false)

  const [brief, setBrief] = useState(
    task?.brief ?? ''
  )

  const [editingBrief, setEditingBrief] =
    useState(false)

  const [estimatedTime, setEstimatedTime] = useState(() => {
  if (task?.estimatedTime == null) return ''

  return String(task.estimatedTime).replace(/[^0-9]/g, '')
})

  const [editingTime, setEditingTime] =
    useState(false)

  const [urgent, setUrgent] =
    useState(false)

  /*
   * --------------------------------------------------
   * TASK NOT FOUND
   * --------------------------------------------------
   */

  if (!task) {
    return (
      <SafeAreaView
        style={[
          styles.empty,
          {
            backgroundColor: t.bg,
          },
        ]}
        edges={['top']}
      >
        <Text
          style={[
            styles.emptyText,
            {
              color: t.muted,
            },
          ]}
        >
          Task not found
        </Text>
      </SafeAreaView>
    )
  }

  /*
   * --------------------------------------------------
   * WORKFLOW
   * --------------------------------------------------
   */

  const toggleStep = (
    index: number
  ) => {
    setSteps(prev =>
      prev.map((step, i) =>
        i === index
          ? {
              ...step,
              done: !step.done,
            }
          : step
      )
    )
  }

  /*
   * --------------------------------------------------
   * COMPLETE TASK
   * --------------------------------------------------
   */

  const handleComplete = async () => {
  try {
    await completeTask(task.id)
    router.back()
  } catch (e) {
    console.error(
      'Failed to complete task:',
      e
    )
  }
}

  /*
   * --------------------------------------------------
   * SECTION NAME
   * --------------------------------------------------
   */

  const sectionName =
    section === 'work'
      ? 'Work'
      : section === 'personal'
        ? 'Personal'
        : 'Leisure'

  return (
    <SafeAreaView
      style={[
        styles.container,
        {
          backgroundColor: t.bg,
        },
      ]}
      edges={['top']}
    >
      {/* Header */}

      <View style={styles.header}>
        <Pressable
          onPress={() => router.back()}
          style={styles.backButton}
        >
          <ChevronLeft
            size={18}
            color={t.muted}
          />

          <Text
            style={[
              styles.backText,
              {
                color: t.muted,
              },
            ]}
          >
            {sectionName}
          </Text>
        </Pressable>

        <View style={styles.titleRow}>
          <View
            style={styles.titleContainer}
          >
            {/* Priority + Risk */}

            <View
              style={styles.badgesRow}
            >
              <View
                style={[
                  styles.priorityBadge,
                  {
                    backgroundColor:
                      `${priorityColors[task.priority]}20`,
                  },
                ]}
              >
                <Text
                  style={[
                    styles.priorityText,
                    {
                      color:
                        priorityColors[
                          task.priority
                        ],
                    },
                  ]}
                >
                  {task.priority}
                </Text>
              </View>

              {task.atRisk && (
                <View
                  style={[
                    styles.riskBadge,
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
                      styles.riskText,
                      {
                        color: t.risk,
                      },
                    ]}
                  >
                    At Risk
                  </Text>
                </View>
              )}
            </View>

            {/* Task title */}

            {editingTitle ? (
              <TextInput
                autoFocus
                value={title}
                onChangeText={setTitle}
                onBlur={async () => {
                  setEditingTitle(false)

                  if (!title.trim()) {
                    setTitle(task.title)
                    return
                  }

                  try {
                    await updateTask(
                      task.id,
                      section,
                      {
                        title:
                          title.trim(),
                      }
                    )
                  } catch (e) {
                    console.error(
                      'Failed to save title:',
                      e
                    )
                  }
                }}
                style={[
                  styles.title,
                  {
                    color: t.text,
                    borderBottomWidth: 1,
                    borderColor:
                      t.primary,
                  },
                ]}
              />
            ) : (
              <Pressable
                onPress={() =>
                  setEditingTitle(true)
                }
                style={{
                  flexDirection:
                    'row',
                  alignItems:
                    'center',
                  gap: 8,
                }}
              >
                <Text
                  style={[
                    styles.title,
                    {
                      color: t.text,
                    },
                  ]}
                >
                  {title}
                </Text>

                <Pencil
                  size={14}
                  color={t.muted}
                />
              </Pressable>
            )}
          </View>
        </View>
      </View>

      {/* Body */}

      <ScrollView
        style={styles.body}
        contentContainerStyle={
          styles.bodyContent
        }
        showsVerticalScrollIndicator={
          false
        }
      >
        {/* Brief */}

        {section === 'work' && (
          <View
            style={[
              styles.brief,
              {
                backgroundColor:
                  t.surface,
                borderColor:
                  t.border,
              },
            ]}
          >
            {editingBrief ? (
              <TextInput
                autoFocus
                value={brief}
                onChangeText={
                  setBrief
                }
                multiline
                onBlur={async () => {
                  setEditingBrief(
                    false
                  )

                  try {
                    await updateTask(
                      task.id,
                      section,
                      {
                        brief:
                          brief.trim() ||
                          null,
                      }
                    )
                  } catch (e) {
                    console.error(
                      'Failed to save brief:',
                      e
                    )
                  }
                }}
                style={[
                  styles.briefText,
                  {
                    color: t.text,
                  },
                ]}
              />
            ) : (
              <Pressable
                onPress={() =>
                  setEditingBrief(
                    true
                  )
                }
                style={{
                  flexDirection:
                    'row',
                  alignItems:
                    'flex-start',
                  gap: 8,
                }}
              >
                <Text
                  style={[
                    styles.briefText,
                    {
                      color:
                        t.muted,
                      flex: 1,
                    },
                  ]}
                >
                  {brief ||
                    'Add a brief...'}
                </Text>

                <Pencil
                  size={12}
                  color={t.muted}
                />
              </Pressable>
            )}
          </View>
        )}

        {/* Deadline */}

        <View
          style={[
            styles.infoCard,
            {
              backgroundColor:
                t.surface,
              borderColor:
                t.border,
            },
          ]}
        >
          <View
            style={
              styles.infoHeader
            }
          >
            <Calendar
              size={13}
              color={t.muted}
            />

            <Text
              style={[
                styles.infoLabel,
                {
                  color: t.muted,
                },
              ]}
            >
              Deadline
            </Text>
          </View>

          <Pressable
            onPress={() =>
              setShowDatePicker(true)
            }
            style={
              styles.editValue
            }
          >
            <Text
              style={[
                styles.valueText,
                {
                  color:
                    deadlineDate
                      ? t.text
                      : t.muted,
                },
              ]}
            >
              {deadlineDate
                ? deadlineDate.toLocaleDateString()
                : 'Set date'}
            </Text>

            <Pencil
              size={12}
              color={t.muted}
            />
          </Pressable>

          {deadlineDate && (
            <Pressable
              onPress={() =>
                setShowTimePicker(
                  true
                )
              }
            >
              <Text
                style={{
                  fontSize: 11,
                  color: t.primary,
                  marginTop: 4,
                }}
              >
                {hasTime
                  ? `Time: ${deadlineDate.toLocaleTimeString(
                      [],
                      {
                        hour: '2-digit',
                        minute: '2-digit',
                      }
                    )} · Change`
                  : '+ Add time (optional)'}
              </Text>
            </Pressable>
          )}
        </View>

        {/* Date Picker */}

        {showDatePicker && (
  <View style={{ backgroundColor: t.surface, borderRadius: 12, marginTop: 8 }}>
    {Platform.OS === 'ios' && (
      <View style={{ flexDirection: 'row', justifyContent: 'flex-end', padding: 8 }}>
        <Pressable onPress={() => setShowDatePicker(false)}>
          <Text style={{ color: t.primary, fontWeight: '600', fontSize: 15 }}>Done</Text>
        </Pressable>
      </View>
    )}

    <DateTimePicker
      value={deadlineDate ?? new Date()}
      mode="date"
      display={Platform.OS === 'ios' ? 'inline' : 'default'}
      themeVariant="light"
      onChange={onDateChange}
    />
  </View>
)}

        {/* Time Picker */}

        {showTimePicker &&
          deadlineDate && (
            <DateTimePicker
              value={
                deadlineDate
              }
              mode="time"
              display={
                Platform.OS === 'ios'
                  ? 'spinner'
                  : 'default'
              }
              themeVariant="light"
              onChange={
                onTimeChange
              }
            />
          )}

        {/* Estimated Time */}

        <View
          style={[
            styles.infoCard,
            {
              backgroundColor:
                t.surface,
              borderColor:
                t.border,
              marginTop: 12,
            },
          ]}
        >
          <View
            style={
              styles.infoHeader
            }
          >
            <Clock
              size={13}
              color={t.muted}
            />

            <Text
              style={[
                styles.infoLabel,
                {
                  color: t.muted,
                },
              ]}
            >
              Estimated Time
            </Text>
          </View>

          {editingTime ? (
            <TextInput
              autoFocus
              value={
                estimatedTime
              }
              onChangeText={val =>
                setEstimatedTime(
                  val.replace(
                    /[^0-9]/g,
                    ''
                  )
                )
              }
              keyboardType="numeric"
              onBlur={async () => {
                setEditingTime(
                  false
                )

                const minutes =
                  parseInt(
                    estimatedTime,
                    10
                  )

                if (
                  isNaN(minutes) ||
                  minutes <= 0
                ) {
                  console.warn(
                    'Invalid time entered, not saving'
                  )
                  return
                }

                try {
                  await updateTask(
                    task.id,
                    section,
                    {
                      estimated_time_minutes:
                        minutes,
                    }
                  )
                } catch (e) {
                  console.error(
                    'Failed to save estimated time:',
                    e
                  )
                }
              }}
              placeholder="e.g. 120"
              placeholderTextColor={
                t.muted
              }
              style={[
                styles.editInput,
                {
                  backgroundColor:
                    t.surface2,
                  color: t.text,
                  borderColor:
                    t.primary,
                },
              ]}
            />
          ) : (
            <Pressable
              onPress={() =>
                setEditingTime(
                  true
                )
              }
              style={
                styles.editValue
              }
            >
              <Text
                style={[
                  styles.valueText,
                  {
                    color:
                      estimatedTime
                        ? t.text
                        : t.muted,
                  },
                ]}
              >
                {estimatedTime
                  ? `${estimatedTime} min`
                  : 'Set estimated time'}
              </Text>

              <Pencil
                size={12}
                color={t.muted}
              />
            </Pressable>
          )}
        </View>

        {/* AI Priority Score */}

        {section === 'work' &&
          task.priorityScore && (
            <View
              style={[
                styles.priorityCard,
                {
                  backgroundColor:
                    `${t.primary}15`,
                  borderColor:
                    `${t.primary}25`,
                },
              ]}
            >
              <View
                style={
                  styles.priorityHeader
                }
              >
                <View
                  style={
                    styles.priorityHeading
                  }
                >
                  <Sparkles
                    size={14}
                    color={
                      t.primary
                    }
                  />

                  <Text
                    style={[
                      styles.priorityLabel,
                      {
                        color:
                          t.primary,
                      },
                    ]}
                  >
                    AI Priority Score
                  </Text>
                </View>

                <View
                  style={[
                    styles.scoreBadge,
                    {
                      backgroundColor:
                        t.primary,
                    },
                  ]}
                >
                  <Text
                    style={
                      styles.score
                    }
                  >
                    {
                      task.priorityScore
                    }
                  </Text>

                  <Text
                    style={
                      styles.scoreTotal
                    }
                  >
                    /100
                  </Text>
                </View>
              </View>

              {task.priorityWhy && (
                <Text
                  style={[
                    styles.priorityWhy,
                    {
                      color:
                        t.muted,
                    },
                  ]}
                >
                  {
                    task.priorityWhy
                  }
                </Text>
              )}
            </View>
          )}

        {/* Workflow */}

        {section === 'work' &&
          steps.length > 0 && (
            <View
              style={
                styles.workflow
              }
            >
              <Text
                style={[
                  styles.workflowLabel,
                  {
                    color:
                      t.muted,
                  },
                ]}
              >
                Workflow
              </Text>

              {steps.map(
                (
                  step,
                  index
                ) => (
                  <Pressable
                    key={index}
                    onPress={() =>
                      toggleStep(
                        index
                      )
                    }
                    style={[
                      styles.step,
                      {
                        backgroundColor:
                          t.surface,
                        borderColor:
                          step.done
                            ? `${t.success}40`
                            : t.border,
                      },
                    ]}
                  >
                    <View
                      style={[
                        styles.checkbox,
                        {
                          backgroundColor:
                            step.done
                              ? t.success
                              : t.surface2,
                          borderColor:
                            step.done
                              ? 'transparent'
                              : t.border,
                        },
                      ]}
                    >
                      {step.done && (
                        <Check
                          size={11}
                          color="#FFFFFF"
                        />
                      )}
                    </View>

                    <Text
                      style={[
                        styles.stepText,
                        {
                          color:
                            step.done
                              ? t.muted
                              : t.text,
                          textDecorationLine:
                            step.done
                              ? 'line-through'
                              : 'none',
                        },
                      ]}
                    >
                      {step.text}
                    </Text>
                  </Pressable>
                )
              )}
            </View>
          )}
      </ScrollView>

      {/* Bottom Actions */}

      <View
        style={[
          styles.actions,
          {
            borderTopColor:
              t.border,
            backgroundColor:
              t.surface,
          },
        ]}
      >
        {/* Mark Urgent */}

        {section === 'work' && (
          <Pressable
            onPress={() =>
              setUrgent(
                value => !value
              )
            }
            style={[
              styles.urgentButton,
              {
                backgroundColor:
                  urgent
                    ? t.riskBg
                    : t.surface2,
                borderColor:
                  urgent
                    ? t.risk
                    : t.border,
              },
            ]}
          >
            <AlertTriangle
              size={16}
              color={
                urgent
                  ? t.risk
                  : t.muted
              }
            />

            <Text
              style={[
                styles.urgentText,
                {
                  color:
                    urgent
                      ? t.risk
                      : t.muted,
                },
              ]}
            >
              {urgent
                ? 'Marked urgent today ✓'
                : 'Mark urgent today'}
            </Text>
          </Pressable>
        )}

        {/* Mark Complete */}

        <Pressable
          onPress={
            handleComplete
          }
          style={[
            styles.completeButton,
            {
              backgroundColor:
                t.success,
            },
          ]}
        >
          <Check
            size={18}
            color="#FFFFFF"
          />

          <Text
            style={
              styles.completeText
            }
          >
            Mark Complete
          </Text>
        </Pressable>
      </View>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },

  header: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 12,
  },

  backButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 16,
  },

  backText: {
    fontSize: 14,
    fontFamily: 'Outfit',
  },

  titleRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
  },

  titleContainer: {
    flex: 1,
  },

  badgesRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },

  priorityBadge: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 999,
  },

  priorityText: {
    fontSize: 12,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 1,
    fontFamily: 'Outfit',
  },

  riskBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 5,
    borderRadius: 999,
  },

  riskText: {
    fontSize: 11,
    fontWeight: '600',
    fontFamily: 'Outfit',
  },

  title: {
    fontSize: 20,
    fontWeight: '700',
    lineHeight: 26,
    fontFamily: 'DM Serif Display',
  },

  body: {
    flex: 1,
  },

  bodyContent: {
    paddingHorizontal: 20,
    paddingBottom: 24,
  },

  brief: {
    padding: 16,
    borderRadius: 16,
    borderWidth: 1,
    marginBottom: 16,
  },

  briefText: {
    fontSize: 14,
    lineHeight: 22,
    fontFamily: 'Outfit',
  },

  infoRow: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 16,
  },

  infoCard: {
    flex: 1,
    borderRadius: 16,
    padding: 14,
    borderWidth: 1,
    minHeight: 84,
  },

  infoHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 6,
  },

  infoLabel: {
    fontSize: 11.5,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    fontFamily: 'Outfit',
  },

  editValue: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },

  valueText: {
    fontSize: 13.5,
    fontWeight: '500',
    flexShrink: 1,
    fontFamily: 'Outfit',
  },

  editInput: {
    width: '100%',
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 5,
    borderWidth: 1.5,
    fontSize: 13.5,
    fontFamily: 'Outfit',
  },

  priorityCard: {
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    marginBottom: 16,
    marginTop: 12,
  },

  priorityHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },

  priorityHeading: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    flex: 1,
  },

  priorityLabel: {
    fontSize: 12,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.7,
    fontFamily: 'Outfit',
  },

  scoreBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
  },

  score: {
    fontSize: 15,
    fontWeight: '700',
    color: '#FFFFFF',
    fontFamily: 'Outfit',
  },

  scoreTotal: {
    fontSize: 11,
    color: 'rgba(255,255,255,0.7)',
    marginLeft: 2,
    fontFamily: 'Outfit',
  },

  priorityWhy: {
    fontSize: 13,
    lineHeight: 20,
    fontFamily: 'Outfit',
  },

  workflow: {
    marginBottom: 16,
  },

  workflowLabel: {
    fontSize: 13,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.7,
    marginBottom: 10,
    fontFamily: 'Outfit',
  },

  step: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
    width: '100%',
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderWidth: 1,
    marginBottom: 8,
  },

  checkbox: {
    width: 20,
    height: 20,
    borderRadius: 999,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1.5,
    marginTop: 1,
  },

  stepText: {
    flex: 1,
    fontSize: 14,
    lineHeight: 20,
    fontFamily: 'Outfit',
  },

  actions: {
    paddingHorizontal: 20,
    paddingVertical: 16,
    borderTopWidth: 1,
    gap: 10,
  },

  urgentButton: {
    width: '100%',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    borderRadius: 12,
    paddingVertical: 14,
    borderWidth: 1.5,
  },

  urgentText: {
    fontSize: 14.5,
    fontWeight: '600',
    fontFamily: 'Outfit',
  },

  completeButton: {
    width: '100%',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    borderRadius: 12,
    paddingVertical: 16,
  },

  completeText: {
    fontSize: 15,
    fontWeight: '700',
    color: '#FFFFFF',
    fontFamily: 'Outfit',
  },

  empty: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },

  emptyText: {
    fontSize: 14,
    fontFamily: 'Outfit',
  },
})