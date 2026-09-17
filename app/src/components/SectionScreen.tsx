import { useState } from 'react'
import {
  View,
  Text,
  ScrollView,
  Pressable,
  StyleSheet,
} from 'react-native'
import { useRouter, type Href } from 'expo-router'
import { SafeAreaView } from 'react-native-safe-area-context'
import { useApp } from '../context/AppContext'
import BottomTabBar from './BottomTabBar'
import FAB from './FAB'
import TaskCard from './TaskCard'
import { Check } from './icons'

interface Props {
  section: 'work' | 'personal' | 'leisure'
}

const sectionConfig = {
  work: {
    title: 'Work',
    subtitle: 'Projects & deliverables',
    emoji: '💼',
  },
  personal: {
    title: 'Personal',
    subtitle: 'Life & errands',
    emoji: '🌿',
  },
  leisure: {
    title: 'Leisure',
    subtitle: 'Rest & recharge',
    emoji: '☕',
  },
}

export default function SectionScreen({ section }: Props) {
  const { t, tasks, completeTask } = useApp()
  const router = useRouter()

  const [completing, setCompleting] =
    useState<string | null>(null)

  const config = sectionConfig[section]
  const sectionTasks = tasks[section]

  const handleComplete = (id: string) => {
    setCompleting(id)

    setTimeout(() => {
      completeTask(id)
      setCompleting(null)
    }, 600)
  }

  return (
    <SafeAreaView
      style={[
        styles.container,
        {
          backgroundColor: t.bg,
        },
      ]}
    >
      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.emoji}>
            {config.emoji}
          </Text>

          <Text
            style={[
              styles.title,
              { color: t.text },
            ]}
          >
            {config.title}
          </Text>

          <Text
            style={[
              styles.subtitle,
              { color: t.muted },
            ]}
          >
            {config.subtitle}
          </Text>
        </View>

        {/* Task count */}
        <View
          style={[
            styles.taskCount,
            {
              backgroundColor: t.surface,
              borderColor: t.border,
            },
          ]}
        >
          <Text
            style={[
              styles.taskCountText,
              { color: t.muted },
            ]}
          >
            {sectionTasks.length} task
            {sectionTasks.length !== 1 ? 's' : ''}
          </Text>
        </View>
      </View>

      {/* Task list */}
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {sectionTasks.length === 0 ? (
          <View style={styles.emptyState}>
            <View
              style={[
                styles.emptyIcon,
                { backgroundColor: t.surface2 },
              ]}
            >
              <Check
                size={22}
                color={t.success}
              />
            </View>

            <Text
              style={[
                styles.emptyText,
                { color: t.muted },
              ]}
            >
              All done! Nothing left here.
            </Text>
          </View>
        ) : (
          <View style={styles.taskList}>
            {sectionTasks.map((task) => (
              <View
                key={task.id}
                style={styles.taskRow}
              >
                {completing === task.id ? (
                  <View
                    style={[
                      styles.completingCard,
                      {
                        backgroundColor:
                          t.successBg,
                        borderColor:
                          t.success,
                      },
                    ]}
                  >
                    <View
                      style={[
                        styles.completedCircle,
                        {
                          backgroundColor:
                            t.success,
                        },
                      ]}
                    >
                      <Check
                        size={14}
                        color="#FFFFFF"
                      />
                    </View>

                    <Text
                      style={[
                        styles.completedTitle,
                        { color: t.muted },
                      ]}
                    >
                      {task.title}
                    </Text>
                  </View>
                ) : (
                  <>
                    {/* Task card */}
                    <View style={styles.cardWrapper}>
                      <TaskCard
                      task={task}
                      variant={section}
                      onTap={() =>
                      router.push(
                        `/task-details?id=${task.id}&section=${task.section}` as Href
                      )
                    }
                    />
                    </View>

                    {/* Complete */}
                    <Pressable
                      onPress={() =>
                        handleComplete(task.id)
                      }
                      style={({ pressed }) => [
                        styles.completeButton,
                        {
                          backgroundColor:
                            t.surface2,
                          borderColor:
                            t.border,
                          transform: [
                            {
                              scale: pressed
                                ? 0.9
                                : 1,
                            },
                          ],
                        },
                      ]}
                    >
                      <Check
                        size={14}
                        color={t.muted}
                      />
                    </Pressable>
                  </>
                )}
              </View>
            ))}
          </View>
        )}

        <View style={styles.bottomSpace} />
      </ScrollView>

      {/* Bottom navigation */}
      <BottomTabBar />

      {/* Add task */}
      <FAB />
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },

  header: {
    paddingHorizontal: 20,
    paddingTop: 20,
    paddingBottom: 16,
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
  },

  emoji: {
    fontSize: 24,
    marginBottom: 2,
  },

  title: {
    fontSize: 22,
    fontWeight: '700',
    lineHeight: 27,
  },

  subtitle: {
    fontSize: 13,
    marginTop: 1,
  },

  taskCount: {
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },

  taskCountText: {
    fontSize: 13,
    fontWeight: '600',
  },

  scroll: {
    flex: 1,
  },

  scrollContent: {
    paddingHorizontal: 20,
    paddingBottom: 16,
  },

  taskList: {
    gap: 10,
  },

  taskRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },

  cardWrapper: {
    flex: 1,
  },

  completeButton: {
    width: 32,
    height: 32,
    borderRadius: 999,
    borderWidth: 1.5,
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: 8,
  },

  completingCard: {
    flex: 1,
    minHeight: 64,
    borderRadius: 16,
    borderWidth: 1.5,
    paddingHorizontal: 16,
    paddingVertical: 16,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    opacity: 0.8,
  },

  completedCircle: {
    width: 28,
    height: 28,
    borderRadius: 999,
    alignItems: 'center',
    justifyContent: 'center',
  },

  completedTitle: {
    flex: 1,
    fontSize: 15,
    textDecorationLine: 'line-through',
  },

  emptyState: {
    height: 192,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
  },

  emptyIcon: {
    width: 52,
    height: 52,
    borderRadius: 999,
    alignItems: 'center',
    justifyContent: 'center',
  },

  emptyText: {
    fontSize: 15,
    textAlign: 'center',
  },

  bottomSpace: {
    height: 80,
  },
})
