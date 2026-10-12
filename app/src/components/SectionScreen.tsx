import React, { useRef, useState } from "react"
import {
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native"
import { SafeAreaView } from "react-native-safe-area-context"
import { GestureHandlerRootView } from "react-native-gesture-handler"
import Reanimated, {
  Extrapolation,
  FadeOut,
  LinearTransition,
  interpolate,
  useAnimatedStyle,
  type SharedValue,
} from "react-native-reanimated"
import ReanimatedSwipeable, {
  type SwipeableMethods,
} from "react-native-gesture-handler/ReanimatedSwipeable"
import { useRouter } from "expo-router"

import { useApp } from "../context/AppContext"
import BottomTabBar from "./BottomTabBar"
import FAB from "./FAB"
import TaskCard from "./TaskCard"
import { Check } from "./icons"
import type { Task } from "../types"

interface Props {
  section: Task["section"]
}

const sectionConfig = {
  work: {
    title: "Work",
    subtitle: "Projects & deliverables",
    emoji: "💼",
  },
  personal: {
    title: "Personal",
    subtitle: "Life & errands",
    emoji: "🌿",
  },
  leisure: {
    title: "Leisure",
    subtitle: "Rest & recharge",
    emoji: "☕",
  },
} as const

export default function SectionScreen({ section }: Props) {
  const router = useRouter()
  const { t, tasks, completeTask, deleteTask, updateTask } = useApp()

  const [completing, setCompleting] = useState<string | null>(null)

  // Only one row stays open at a time (like WhatsApp / iOS Mail):
  // opening a row closes the previous one.
  const openRow = useRef<SwipeableMethods | null>(null)

  const config = sectionConfig[section]
  const sectionTasks = tasks[section]

  const handleComplete = (id: string) => {
    setCompleting(id)

    setTimeout(async () => {
      try {
        await completeTask(id)
      } catch (error) {
        console.error("Failed to complete task:", error)
        Alert.alert("Could not complete task", "Please try again.")
      } finally {
        setCompleting(null)
      }
    }, 350)
  }

  const handleDelete = (task: Task) => {
    Alert.alert(
      "Delete task?",
      `Delete “${task.title}”? This cannot be undone.`,
      [
        {
          text: "Cancel",
          style: "cancel",
        },
        {
          text: "Delete",
          style: "destructive",
          onPress: () => {
            void deleteTask(task.id, task.section).catch((error) => {
              console.error("Failed to delete task:", error)
              Alert.alert("Could not delete task", "Please try again.")
            })
          },
        },
      ],
    )
  }

  const handleBlock = (task: Task) => {
    void updateTask(task.id, task.section, {
      isBlocked: !task.isBlocked,
    }).catch((error) => {
      console.error("Failed to update task:", error)
      Alert.alert("Could not update task", "Please try again.")
    })
  }

  const handleTaskTap = (task: Task) => {
    router.push(`/task-details?id=${task.id}&section=${task.section}`)
  }

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
    <SafeAreaView
      edges={["top"]}
      style={[styles.container, { backgroundColor: t.bg }]}
    >
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Text style={styles.emoji}>{config.emoji}</Text>

          <Text style={[styles.title, { color: t.text }]}>
            {config.title}
          </Text>

          <Text style={[styles.subtitle, { color: t.muted }]}>
            {config.subtitle}
          </Text>
        </View>

        <View
          style={[
            styles.countBadge,
            {
              backgroundColor: t.surface,
              borderColor: t.border,
            },
          ]}
        >
          <Text style={[styles.countText, { color: t.muted }]}>
            {sectionTasks.length} task
            {sectionTasks.length !== 1 ? "s" : ""}
          </Text>
        </View>
      </View>

      {/* Task list */}
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        onScrollBeginDrag={() => openRow.current?.close()}
      >
        {sectionTasks.length === 0 ? (
          <View style={styles.emptyState}>
            <View
              style={[styles.emptyIcon, { backgroundColor: t.surface2 }]}
            >
              <Check size={22} color={t.success} />
            </View>

            <Text style={[styles.emptyText, { color: t.muted }]}>
              All done! Nothing left here.
            </Text>
          </View>
        ) : (
          <View style={styles.taskList}>
            {sectionTasks.map((task) => (
              // When a task leaves the list, the rows below glide up
              // instead of jumping.
              <Reanimated.View
                key={task.id}
                layout={LinearTransition.springify().damping(22)}
                exiting={FadeOut.duration(180)}
              >
                {completing === task.id ? (
                  <View
                    style={[
                      styles.completedRow,
                      {
                        backgroundColor: t.successBg,
                        borderColor: `${t.success}40`,
                      },
                    ]}
                  >
                    <View
                      style={[
                        styles.completedIcon,
                        { backgroundColor: t.success },
                      ]}
                    >
                      <Check size={14} color="#FFFFFF" />
                    </View>

                    <Text
                      style={[styles.completedTitle, { color: t.muted }]}
                    >
                      {task.title}
                    </Text>
                  </View>
                ) : (
                  <SwipeTaskRow
                    task={task}
                    openRow={openRow}
                    onOpen={() => handleTaskTap(task)}
                    onComplete={() => handleComplete(task.id)}
                    onBlock={() => handleBlock(task)}
                    onDelete={() => handleDelete(task)}
                  />
                )}
              </Reanimated.View>
            ))}
          </View>
        )}
      </ScrollView>

      <BottomTabBar />
      <FAB />
        </SafeAreaView>
    </GestureHandlerRootView>
)
}

/* -------------------------------------------------------------------------- */
/* Swipe row                                                                  */
/*                                                                            */
/* Swipe right -> Complete. Swipe left -> Block / Unblock and Delete.         */
/* The drag runs on the native/UI thread (no JS thread in the loop), with     */
/* friction, spring snap and rubber-band overshoot, so it stays smooth.       */
/* -------------------------------------------------------------------------- */

function SwipeTaskRow({
  task,
  openRow,
  onOpen,
  onComplete,
  onBlock,
  onDelete,
}: {
  task: Task
  openRow: React.MutableRefObject<SwipeableMethods | null>
  onOpen: () => void
  onComplete: () => void
  onBlock: () => void
  onDelete: () => void
}) {
  const { t } = useApp()

  const swipeRef = useRef<SwipeableMethods>(null)
  const isOpen = useRef(false)

  const closeRow = () => swipeRef.current?.close()

  return (
    <ReanimatedSwipeable
      ref={swipeRef}
      friction={2}
      overshootFriction={8}
      leftThreshold={40}
      rightThreshold={40}
      containerStyle={styles.swipeContainer}
      onSwipeableWillOpen={() => {
        if (openRow.current && openRow.current !== swipeRef.current) {
          openRow.current.close()
        }
        openRow.current = swipeRef.current
        isOpen.current = true
      }}
      onSwipeableClose={() => {
        isOpen.current = false
        if (openRow.current === swipeRef.current) {
          openRow.current = null
        }
      }}
      renderLeftActions={(progress) => (
        <ActionPane
          progress={progress}
          color={t.success}
          label="Complete"
          showCheck
          onPress={() => {
            closeRow()
            onComplete()
          }}
        />
      )}
      renderRightActions={(progress) => (
        <View style={styles.rightActions}>
          <ActionPane
            progress={progress}
            width={76}
            color={task.isBlocked ? t.surface2 : "#FFF7D6"}
            textColor={task.isBlocked ? t.muted : "#9A7A00"}
            label={task.isBlocked ? "Unblock" : "Block"}
            onPress={() => {
              closeRow()
              onBlock()
            }}
          />

          <ActionPane
            progress={progress}
            width={69}
            color={t.risk}
            label="Delete"
            onPress={() => {
              closeRow()
              onDelete()
            }}
          />
        </View>
      )}
    >
      <TaskCard
        task={task}
        variant={task.section}
        onTap={() => {
          // a tap on an open row only closes it
          if (isOpen.current) {
            closeRow()
            return
          }
          onOpen()
        }}
      />
    </ReanimatedSwipeable>
  )
}

function ActionPane({
  progress,
  color,
  label,
  width = 92,
  textColor = "#FFFFFF",
  showCheck,
  onPress,
}: {
  progress: SharedValue<number>
  color: string
  label: string
  width?: number
  textColor?: string
  showCheck?: boolean
  onPress: () => void
}) {
  // The label fades and scales in while the row is dragged open
  const contentStyle = useAnimatedStyle(() => ({
    opacity: interpolate(
      progress.value,
      [0, 0.5, 1],
      [0, 0.7, 1],
      Extrapolation.CLAMP,
    ),
    transform: [
      {
        scale: interpolate(
          progress.value,
          [0, 1],
          [0.7, 1],
          Extrapolation.CLAMP,
        ),
      },
    ],
  }))

  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={[styles.actionPane, { width, backgroundColor: color }]}
    >
      <Reanimated.View style={[styles.actionContent, contentStyle]}>
        {showCheck ? <Check size={16} color="#FFFFFF" /> : null}
        <Text style={[styles.actionLabel, { color: textColor }]}>{label}</Text>
      </Reanimated.View>
    </Pressable>
  )
}

/* -------------------------------------------------------------------------- */
/* Styles                                                                     */
/* -------------------------------------------------------------------------- */

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },

  header: {
    paddingHorizontal: 20,
    paddingTop: 20,
    paddingBottom: 16,
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
  },

  headerLeft: {
    flex: 1,
  },

  emoji: {
    fontSize: 24,
    marginBottom: 2,
  },

  title: {
    fontSize: 22,
    fontWeight: "700",
    marginBottom: 2,
  },

  subtitle: {
    fontSize: 13,
    marginTop: 1,
  },

  countBadge: {
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderWidth: 1,
    marginLeft: 12,
  },

  countText: {
    fontSize: 13,
    fontWeight: "600",
  },

  scroll: {
    flex: 1,
  },

  scrollContent: {
    paddingHorizontal: 20,
    paddingBottom: 20,
  },

  taskList: {
    gap: 10,
  },

  emptyState: {
    height: 192,
    alignItems: "center",
    justifyContent: "center",
    gap: 12,
  },

  emptyIcon: {
    width: 52,
    height: 52,
    borderRadius: 26,
    alignItems: "center",
    justifyContent: "center",
  },

  emptyText: {
    fontSize: 15,
    textAlign: "center",
  },

  completedRow: {
    minHeight: 62,
    borderRadius: 16,
    borderWidth: 1.5,
    paddingHorizontal: 16,
    paddingVertical: 16,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    opacity: 0.8,
  },

  completedIcon: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
  },

  completedTitle: {
    flex: 1,
    fontSize: 15,
    textDecorationLine: "line-through",
  },

  /* Swipe row */

  swipeContainer: {
    borderRadius: 16,
    overflow: "hidden",
  },

  rightActions: {
    flexDirection: "row",
  },

  actionPane: {
    alignItems: "center",
    justifyContent: "center",
  },

  actionContent: {
    alignItems: "center",
    justifyContent: "center",
    gap: 4,
  },

  actionLabel: {
    color: "#FFFFFF",
    fontSize: 12,
    fontWeight: "600",
  },
})