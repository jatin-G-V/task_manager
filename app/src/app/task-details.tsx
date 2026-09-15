import React, { useState } from 'react'
import type { Task } from '../types'
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

const { tasks, t, completeTask } = useApp()

const task = tasks[section].find(item => item.id === id)

  const [steps, setSteps] = useState(
    task?.steps?.map(s => ({ text: s, done: false })) ?? []
  )
  const [deadline, setDeadline] = useState(task?.deadline ?? '')
  const [editingDeadline, setEditingDeadline] = useState(false)

  const [estimatedTime, setEstimatedTime] = useState(
    task?.estimatedTime ?? ''
  )
  const [editingTime, setEditingTime] = useState(false)

  const [urgent, setUrgent] = useState(false)

  if (!task) {
    return (
      <View style={[styles.empty, { backgroundColor: t.bg }]}>
        <Text style={[styles.emptyText, { color: t.muted }]}>
          Task not found
        </Text>
      </View>
    )
  }

  const toggleStep = (index: number) => {
    setSteps(prev =>
      prev.map((step, i) =>
        i === index
          ? { ...step, done: !step.done }
          : step
      )
    )
  }

  const handleComplete = () => {
    completeTask(task.id)
    router.back()
  }


  const sectionName =
    section === 'work'
      ? 'Work'
      : section === 'personal'
        ? 'Personal'
        : 'Leisure'

  return (
    <View style={[styles.container, { backgroundColor: t.bg }]}>

      {/* Header */}
      <View style={styles.header}>

        <Pressable
          onPress={() => router.back()}
          style={styles.backButton}
        >
          <ChevronLeft size={18} color={t.muted} />

          <Text
            style={[
              styles.backText,
              { color: t.muted },
            ]}
          >
            {sectionName}
          </Text>
        </Pressable>

        <View style={styles.titleRow}>

          <View style={styles.titleContainer}>

            {/* Priority + Risk */}
            <View style={styles.badgesRow}>

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
                        priorityColors[task.priority],
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
                      backgroundColor: t.riskBg,
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
                      { color: t.risk },
                    ]}
                  >
                    At Risk
                  </Text>
                </View>
              )}

            </View>

            {/* Task title */}
            <Text
              style={[
                styles.title,
                { color: t.text },
              ]}
            >
              {task.title}
            </Text>

          </View>

        </View>
      </View>

      {/* Body */}
      <ScrollView
        style={styles.body}
        contentContainerStyle={styles.bodyContent}
        showsVerticalScrollIndicator={false}
      >

        {/* Brief */}
        {section === 'work' && task.brief && (
          <View
            style={[
              styles.brief,
              {
                backgroundColor: t.surface,
                borderColor: t.border,
              },
            ]}
          >
            <Text
              style={[
                styles.briefText,
                { color: t.muted },
              ]}
            >
              {task.brief}
            </Text>
          </View>
        )}

        {/* Deadline + Time */}
        <View style={styles.infoRow}>

          {/* Deadline */}
          <View
            style={[
              styles.infoCard,
              {
                backgroundColor: t.surface,
                borderColor: t.border,
              },
            ]}
          >
            <View style={styles.infoHeader}>
              <Calendar size={13} color={t.muted} />

              <Text
                style={[
                  styles.infoLabel,
                  { color: t.muted },
                ]}
              >
                Deadline
              </Text>
            </View>

            {editingDeadline ? (
              <TextInput
                autoFocus
                value={deadline}
                onChangeText={setDeadline}
                onBlur={() =>
                  setEditingDeadline(false)
                }
                style={[
                  styles.editInput,
                  {
                    backgroundColor: t.surface2,
                    color: t.text,
                    borderColor: t.primary,
                  },
                ]}
              />
            ) : (
              <Pressable
                onPress={() =>
                  setEditingDeadline(true)
                }
                style={styles.editValue}
              >
                <Text
                  style={[
                    styles.valueText,
                    { color: t.text },
                  ]}
                >
                  {deadline}
                </Text>

                <Pencil
                  size={12}
                  color={t.muted}
                />
              </Pressable>
            )}
          </View>

          {/* Estimated Time - Work */}
          {section === 'work' && (
            <View
              style={[
                styles.infoCard,
                {
                  backgroundColor: t.surface,
                  borderColor: t.border,
                },
              ]}
            >
              <View style={styles.infoHeader}>
                <Clock size={13} color={t.muted} />

                <Text
                  style={[
                    styles.infoLabel,
                    { color: t.muted },
                  ]}
                >
                  Est. Time
                </Text>
              </View>

              {editingTime ? (
                <TextInput
                  autoFocus
                  value={estimatedTime}
                  onChangeText={setEstimatedTime}
                  onBlur={() =>
                    setEditingTime(false)
                  }
                  placeholder="e.g. 2 hours"
                  placeholderTextColor={t.muted}
                  style={[
                    styles.editInput,
                    {
                      backgroundColor: t.surface2,
                      color: t.text,
                      borderColor: t.primary,
                    },
                  ]}
                />
              ) : (
                <Pressable
                  onPress={() =>
                    setEditingTime(true)
                  }
                  style={styles.editValue}
                >
                  <Text
                    style={[
                      styles.valueText,
                      {
                        color: estimatedTime
                          ? t.text
                          : t.muted,
                      },
                    ]}
                  >
                    {estimatedTime || 'Set time'}
                  </Text>

                  <Pencil
                    size={12}
                    color={t.muted}
                  />
                </Pressable>
              )}
            </View>
          )}

          {/* Scheduled Time - Leisure */}
          {section === 'leisure' &&
            task.scheduledTime && (
              <View
                style={[
                  styles.infoCard,
                  {
                    backgroundColor: t.surface,
                    borderColor: t.border,
                  },
                ]}
              >
                <View style={styles.infoHeader}>
                  <Clock
                    size={13}
                    color={t.muted}
                  />

                  <Text
                    style={[
                      styles.infoLabel,
                      { color: t.muted },
                    ]}
                  >
                    Scheduled
                  </Text>
                </View>

                <Text
                  style={[
                    styles.valueText,
                    { color: t.text },
                  ]}
                >
                  {task.scheduledTime}
                </Text>
              </View>
            )}

        </View>

        {/* AI Priority Score */}
        {section === 'work' &&
          task.priorityScore && (
            <View
              style={[
                styles.priorityCard,
                {
                  backgroundColor: `${t.primary}15`,
                  borderColor: `${t.primary}25`,
                },
              ]}
            >
              <View style={styles.priorityHeader}>

                <View style={styles.priorityHeading}>
                  <Sparkles
                    size={14}
                    color={t.primary}
                  />

                  <Text
                    style={[
                      styles.priorityLabel,
                      { color: t.primary },
                    ]}
                  >
                    AI Priority Score
                  </Text>
                </View>

                <View
                  style={[
                    styles.scoreBadge,
                    {
                      backgroundColor: t.primary,
                    },
                  ]}
                >
                  <Text style={styles.score}>
                    {task.priorityScore}
                  </Text>

                  <Text style={styles.scoreTotal}>
                    /100
                  </Text>
                </View>

              </View>

              {task.priorityWhy && (
                <Text
                  style={[
                    styles.priorityWhy,
                    { color: t.muted },
                  ]}
                >
                  {task.priorityWhy}
                </Text>
              )}

            </View>
          )}

        {/* Workflow */}
        {section === 'work' &&
          steps.length > 0 && (
            <View style={styles.workflow}>

              <Text
                style={[
                  styles.workflowLabel,
                  { color: t.muted },
                ]}
              >
                Workflow
              </Text>

              {steps.map((step, index) => (
                <Pressable
                  key={index}
                  onPress={() =>
                    toggleStep(index)
                  }
                  style={[
                    styles.step,
                    {
                      backgroundColor: t.surface,
                      borderColor: step.done
                        ? `${t.success}40`
                        : t.border,
                    },
                  ]}
                >
                  <View
                    style={[
                      styles.checkbox,
                      {
                        backgroundColor: step.done
                          ? t.success
                          : t.surface2,
                        borderColor: step.done
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
                        color: step.done
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
              ))}

            </View>
          )}

      </ScrollView>

      {/* Bottom Actions */}
      <View
        style={[
          styles.actions,
          {
            borderTopColor: t.border,
            backgroundColor: t.surface,
          },
        ]}
      >

        {/* Mark Urgent */}
        {section === 'work' && (
          <Pressable
            onPress={() =>
              setUrgent(value => !value)
            }
            style={[
              styles.urgentButton,
              {
                backgroundColor: urgent
                  ? t.riskBg
                  : t.surface2,
                borderColor: urgent
                  ? t.risk
                  : t.border,
              },
            ]}
          >
            <AlertTriangle
              size={16}
              color={
                urgent ? t.risk : t.muted
              }
            />

            <Text
              style={[
                styles.urgentText,
                {
                  color: urgent
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
          onPress={handleComplete}
          style={[
            styles.completeButton,
            {
              backgroundColor: t.success,
            },
          ]}
        >
          <Check
            size={18}
            color="#FFFFFF"
          />

          <Text style={styles.completeText}>
            Mark Complete
          </Text>
        </Pressable>

      </View>
    </View>
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