import React, {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react'



import {

  View,

  Text,

  ScrollView,

  Pressable,

  StyleSheet,

} from 'react-native'



import {

  useSafeAreaInsets,

  SafeAreaView,

} from 'react-native-safe-area-context'



import { useRouter, useFocusEffect, type Href } from 'expo-router'



import { useApp } from '../context/AppContext'



import BottomTabBar from '../components/BottomTabBar'

import FAB from '../components/FAB'

import { whenLabel, reasonLabel, greeting } from '../utils/taskTime'
import { recurrenceLabel } from '../utils/taskFormat'

import {

  AlertTriangle,

  Check,

  ChevronRight,

  Sparkles,

  UserCircle,

} from '../components/icons'



import type {

  EnergyLevel,

  Task,

} from '../types'





// ============================================================

// HELPERS

// ============================================================







const energyOptions: {

  value: Exclude<EnergyLevel, null>

  label: string

}[] = [

  {

    value: 'low',

    label: 'Low energy',

  },

  {

    value: 'focused',

    label: 'Focused',

  },

  {

    value: 'high',

    label: 'High energy',

  },

]





// ============================================================

const DIGEST_ROUTE = '/dailyDigest' as Href
const OVERDUE_ROUTE = '/overDue' as Href


// DASHBOARD

// ============================================================



export default function DashboardScreen() {
  const {
    t,
    user,
    dueTodayCount,
    atRiskCount,
    suggestedList,
    rankedTasks,
    overdueTasks,
    tasks,
    completeTask,
    refreshTasks,
    energy,
    setEnergy,
  } = useApp()

  const router = useRouter()
  const insets = useSafeAreaInsets()

  useFocusEffect(
    useCallback(() => {
      refreshTasks()
      const id = setInterval(refreshTasks, 5 * 60 * 1000)
      return () => clearInterval(id)
    }, [])
  )

  const allTasks = useMemo(
    () => [...tasks.work, ...tasks.personal, ...tasks.leisure],
    [tasks]
  )

  const [skip, setSkip] = useState(0)

  const candidates = useMemo(() => {
    const seen = new Set(suggestedList.map((x) => x.id))
    return [...suggestedList, ...rankedTasks.filter((x) => !seen.has(x.id))]
  }, [suggestedList, rankedTasks])

  useEffect(() => {
    setSkip(0)
  }, [suggestedList])

  const upNext = candidates.length > 0 ? candidates[skip % candidates.length] : null

  const showSomethingElse = () => setSkip((s) => s + 1)

  const visibleTasks = useMemo(
    () => rankedTasks.filter((x) => x.id !== upNext?.id),
    [rankedTasks, upNext?.id]
  )

  const toggleEnergy = (value: Exclude<EnergyLevel, null>) => {
    setSkip(0)
    setEnergy(energy === value ? null : value)
  }

  const handleComplete = async (id: string) => {
    try {
      await completeTask(id)
    } catch (error) {
      console.error('Complete failed:', error)
    }
  }

  const dayOfWeek = new Date().toLocaleDateString('en-US', { weekday: 'long' })
  const dateStr = new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric' })

  const reschedule = (title: string) =>
    router.push({
      pathname: '/ChatScreen',
      params: { prefill: `Reschedule ${title} to ` },
    })

// RENDER

  // ==========================================================



  return (

    <View

      style={[

        styles.container,

        {

          backgroundColor:

            t.bg,

        },

      ]}

    >

      <SafeAreaView

        style={styles.safeArea}

        edges={['top']}

      >

        <ScrollView

          showsVerticalScrollIndicator={

            false

          }

          contentContainerStyle={[

            styles.scrollContent,

            {

              paddingBottom:

                100 + insets.bottom,

            },

          ]}

        >



          {/* ==================================================

              HEADER

          ================================================== */}



          <View

            style={styles.header}

          >

            <View

              style={

                styles.headerTextContainer

              }

            >

              <Text

                style={[

                  styles.greeting,

                  {

                    color: t.text,

                  },

                ]}

              >

                {greeting(user.name)}

              </Text>



              <Text

                style={[

                  styles.date,

                  {

                    color: t.muted,

                  },

                ]}

              >

                {dayOfWeek},{' '}

                {dateStr}

              </Text>

            </View>



            <Pressable

              onPress={() =>

                router.push(

                  '/menu'

                )

              }

              style={({ pressed }) => [

                styles.profileButton,

                {

                  backgroundColor:

                    t.surface,

                  borderColor:

                    t.border,

                },

                pressed &&

                  styles.pressed,

              ]}

            >

              <UserCircle

                size={22}

                color={t.muted}

              />

            </Pressable>

          </View>





          {/* ==================================================

              DAILY DIGEST

          ================================================== */}



          <Pressable
            onPress={() => router.push(DIGEST_ROUTE)}
            style={({ pressed }) => [
              styles.digestCard,
              {
                backgroundColor: t.surface,
                borderColor: t.border,
              },
              pressed && styles.pressed,
            ]}
          >
            <View style={styles.digestContent}>
              {/* Due today */}
              <View style={styles.digestItem}>
                <View
                  style={[
                    styles.statusDot,
                    { backgroundColor: t.due },
                  ]}
                />

                <Text
                  style={[
                    styles.digestText,
                    { color: t.text },
                  ]}
                >
                  <Text
                    style={[
                      styles.digestNumber,
                      { color: t.due },
                    ]}
                  >
                    {dueTodayCount}
                  </Text>{' '}
                  due today
                </Text>
              </View>

              <View
                style={[
                  styles.digestDivider,
                  { backgroundColor: t.border },
                ]}
              />

              {/* At risk */}
              <View style={styles.digestItem}>
                <View
                  style={[
                    styles.statusDot,
                    { backgroundColor: t.risk },
                  ]}
                />

                <Text
                  style={[
                    styles.digestText,
                    { color: t.text },
                  ]}
                >
                  <Text
                    style={[
                      styles.digestNumber,
                      { color: t.risk },
                    ]}
                  >
                    {atRiskCount}
                  </Text>{' '}
                  at risk
                </Text>
              </View>
            </View>

            <ChevronRight
              size={16}
              color={t.muted}
            />
          </Pressable>





          {/* ==================================================

              LOADING / EMPTY

          ================================================== */}



          {allTasks.length === 0 ? (

            <View

              style={[

                styles.emptyCard,

                {

                  backgroundColor:

                    t.surface,

                  borderColor:

                    t.border,

                },

              ]}

            >

              <Sparkles

                size={22}

                color={t.primary}

              />



              <Text

                style={[

                  styles.emptyTitle,

                  {

                    color:

                      t.text,

                  },

                ]}

              >

                Your day is clear.

              </Text>



              <Text

                style={[

                  styles.emptySubtitle,

                  {

                    color:

                      t.muted,

                  },

                ]}

              >

                Add a task and I'll

                help you decide what

                to do next.

              </Text>



              <Pressable

                onPress={() =>

                  router.push(

                    '/ChatScreen'

                  )

                }

                style={({ pressed }) => [

                  styles.emptyButton,

                  {

                    backgroundColor:

                      t.primary,

                  },

                  pressed &&

                    styles.pressed,

                ]}

              >

                <Text

                  style={

                    styles.emptyButtonText

                  }

                >

                  Tell me your first task

                </Text>

              </Pressable>

            </View>

          ) : (

            <>



              {/* ==================================================

                  SUGGESTED / UP NEXT

              ================================================== */}



              {upNext && (

                <View

                  style={

                    styles.section

                  }

                >

                  <View

                    style={

                      styles.sectionHeader

                    }

                  >

                    <View

                      style={

                        styles.sectionTitleRow

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

                          styles.sectionTitle,

                          {

                            color:

                              t.text,

                          },

                        ]}

                      >

                        Up next

                      </Text>

                    </View>

                  </View>





                  <View

                    style={[

                      styles.suggestedCard,

                      {

                        backgroundColor:

                          t.surface,

                        borderColor:

                          `${t.primary}45`,

                      },

                    ]}

                  >



                    {/* Top row */}



                    <View

                      style={

                        styles.suggestedTopRow

                      }

                    >

                      <View

                        style={[

                          styles.reasonBadge,

                          {

                            backgroundColor:

                              t.dueBg,

                          },

                        ]}

                      >

                        <Text

                          style={[

                            styles.reasonText,

                            {

                              color:

                                t.due,

                            },

                          ]}

                        >

                          {reasonLabel(upNext.reason)}

                        </Text>

                      </View>



                      <Text

                        style={[

                          styles.sectionName,

                          {

                            color:

                              t.muted,

                          },

                        ]}

                      >

                        {

                          upNext.section

                        }

                      </Text>

                    </View>





                    {/* Task title */}



                    <Pressable

                      onPress={() =>

                        router.push({

                          pathname:

                            '/task-details',

                          params: {

                            id:

                              upNext.id,

                            section:

                              upNext.section,

                          },

                        })

                      }

                      style={({ pressed }) => [

                        styles.suggestedTaskButton,

                        pressed &&

                          styles.pressed,

                      ]}

                    >

                      <Text

                        numberOfLines={

                          2

                        }

                        style={[

                          styles.suggestedTitle,

                          {

                            color:

                              t.text,

                          },

                        ]}

                      >

                        {

                          upNext.title

                        }

                      </Text>



                      <Text

                        style={[

                          styles.suggestedDeadline,

                          {

                            color:

                              t.muted,

                          },

                        ]}

                      >

                        {whenLabel(upNext)}

                      </Text>

                    </Pressable>





                    {/* Actions */}



                    <View

                      style={

                        styles.actionRow

                      }

                    >

                      <Pressable

                        onPress={() => handleComplete(upNext.id)}

                        style={({ pressed }) => [

                          styles.primaryAction,

                          {

                            backgroundColor:

                              t.primary,

                          },

                          pressed &&

                            styles.pressed,

                        ]}

                      >

                        <Check

                          size={14}

                          color="#FFFFFF"

                        />



                        <Text

                          style={

                            styles.primaryActionText

                          }

                        >

                          Complete

                        </Text>

                      </Pressable>





                      <Pressable

                        onPress={showSomethingElse}

                        disabled={candidates.length < 2}

                        style={({ pressed }) => [

                          styles.secondaryAction,

                          {

                            backgroundColor:

                              t.surface2,

                            borderColor:

                              t.border,

                          },

                          pressed &&

                            styles.pressed,

                        ]}

                      >

                        <Text

                          style={[

                            styles.secondaryActionText,

                            {

                              color:

                                t.text,

                            },

                          ]}

                        >

                          Something else

                        </Text>

                      </Pressable>

                    </View>





                    {/* Energy */}



                    <View

                      style={

                        styles.energyRow

                      }

                    >

                      {energyOptions.map(

                        (option) => {

                          const selected =

                            energy ===

                            option.value



                          return (

                            <Pressable

                              key={

                                option.value

                              }

                              onPress={() =>

                                toggleEnergy(

                                  option.value

                                )

                              }

                              style={({ pressed }) => [

                                styles.energyChip,

                                {

                                  backgroundColor:

                                    selected

                                      ? t.primary

                                      : t.surface2,

                                  borderColor:

                                    selected

                                      ? t.primary

                                      : t.border,

                                },

                                pressed &&

                                  styles.pressed,

                              ]}

                            >

                              <Text

                                style={[

                                  styles.energyText,

                                  {

                                    color:

                                      selected

                                        ? '#FFFFFF'

                                        : t.muted,

                                  },

                                ]}

                              >

                                {

                                  option.label

                                }

                              </Text>

                            </Pressable>

                          )

                        }

                      )}

                    </View>



                  </View>

                </View>

              )}





              {/* ==================================================

                  OVERDUE

              ================================================== */}



              {overdueTasks.length >

                0 && (

                <View

                  style={

                    styles.section

                  }

                >

                  <View

                    style={

                      styles.sectionHeader

                    }

                  >

                    <View

                      style={

                        styles.sectionTitleRow

                      }

                    >

                      <AlertTriangle

                        size={14}

                        color={t.risk}

                      />



                      <Text

                        style={[

                          styles.sectionTitle,

                          {

                            color:

                              t.text,

                          },

                        ]}

                      >

                        Overdue

                      </Text>

                    </View>



                    <View

                      style={[

                        styles.overdueBadge,

                        {

                          backgroundColor:

                            t.riskBg,

                        },

                      ]}

                    >

                      <Text

                        style={[

                          styles.overdueBadgeText,

                          {

                            color:

                              t.risk,

                          },

                        ]}

                      >

                        {

                          overdueTasks.length

                        } overdue

                      </Text>

                    </View>

                  </View>





                  {overdueTasks.slice(0, 2).map((task) => (
                  <OverdueRow
                    key={task.id}
                    task={task}
                    when={whenLabel(task)}
                    onOpen={() =>
                      router.push({
                        pathname: '/task-details',
                        params: { id: task.id, section: task.section },
                      })
                    }
                    onComplete={() => handleComplete(task.id)}
                    onReschedule={() => reschedule(task.title)}
                    t={t}
                  />
                ))}

                {overdueTasks.length > 2 && (
                  <Pressable onPress={() => router.push(OVERDUE_ROUTE)}>
                    <Text style={{ color: t.risk, fontSize: 12, marginTop: 8 }}>
                      See all {overdueTasks.length} overdue
                    </Text>
                  </Pressable>
                )}
              </View>
            )}

            {/* ==================================================
                ALL TASKS
              ================================================== */}



              {visibleTasks.length >

                0 && (

                <View

                  style={

                    styles.section

                  }

                >

                  <View

                    style={

                      styles.sectionHeader

                    }

                  >

                    <Text

                      style={[

                        styles.sectionTitle,

                        {

                          color:

                            t.text,

                        },

                      ]}

                    >

                      Next up

                    </Text>



                    <Text

                      style={[

                        styles.taskCount,

                        {

                          color:

                            t.muted,

                        },

                      ]}

                    >

                      Top{' '}

                      {Math.min(

                        4,

                        visibleTasks.length

                      )}{' '}

                      of{' '}

                      {

                        visibleTasks.length

                      }

                    </Text>

                  </View>





                  <View

                    style={[

                      styles.taskList,

                      {

                        backgroundColor:

                          t.surface,

                        borderColor:

                          t.border,

                      },

                    ]}

                  >

                    {visibleTasks

                      .slice(0, 4)

                      .map(

                        (

                          task,

                          index

                        ) => (

                          <CompactTaskRow

                            key={

                              task.id

                            }

                            task={

                              task

                            }

                            showDivider={

                              index > 0

                            }

                            onOpen={() =>

                              router.push({

                                pathname:

                                  '/task-details',

                                params: {

                                  id:

                                    task.id,

                                  section:

                                    task.section,

                                },

                              })

                            }

                            onComplete={() =>

                              handleComplete(task.id)

                            }

                            t={t}

                          />

                        )

                      )}

                  </View>

                </View>

              )}



            </>

          )}



        </ScrollView>

      </SafeAreaView>





      {/* ========================================================

          EXISTING NAVIGATION / FAB

          ======================================================== */}



      <BottomTabBar />

      <FAB />



    </View>

  )

}





// ============================================================

// OVERDUE ROW

// ============================================================



function OverdueRow({

  task,

  when,

  onOpen,

  onComplete,

  onReschedule,

  t,

}: {

  task: Task

  when: string

  onOpen: () => void

  onComplete: () => void

  onReschedule: () => void

  t: any

}) {

  return (

    <View

      style={[

        styles.overdueRow,

        {

          backgroundColor:

            t.riskBg,

          borderColor:

            `${t.risk}45`,

        },

      ]}

    >

      <Pressable

        onPress={onOpen}

        style={({ pressed }) => [

          styles.overdueTaskButton,

          pressed &&

            styles.pressed,

        ]}

      >

        <Text

          numberOfLines={1}

          style={[

            styles.overdueTitle,

            {

              color:

                t.text,

            },

          ]}

        >

          {task.title}

        </Text>



        <Text

          style={[

            styles.overdueSubtitle,

            {

              color:

                t.risk,

            },

          ]}

        >

          {recurrenceLabel(task)
            ? `${when} · ${recurrenceLabel(task)}`
            : when}

        </Text>

      </Pressable>





      <Pressable

        onPress={onReschedule}

        style={({ pressed }) => [

          styles.rescheduleButton,

          {

            backgroundColor:

              t.surface,

          },

          pressed &&

            styles.pressed,

        ]}

      >

        <Text

          style={[

            styles.rescheduleText,

            {

              color:

                t.risk,

            },

          ]}

        >

          Reschedule

        </Text>

      </Pressable>





      <Pressable

        onPress={onComplete}

        accessibilityLabel={`Complete ${task.title}`}

        style={({ pressed }) => [

          styles.completeSmallButton,

          {

            backgroundColor:

              t.surface,

          },

          pressed &&

            styles.pressed,

        ]}

      >

        <Check

          size={13}

          color={t.success}

        />

      </Pressable>

    </View>

  )

}





// ============================================================

// COMPACT TASK ROW

// ============================================================



function CompactTaskRow({

  task,

  showDivider,

  onOpen,

  onComplete,

  t,

}: {

  task: Task

  showDivider: boolean

  onOpen: () => void

  onComplete: () => void

  t: any

}) {

  return (

    <View

      style={[

        styles.taskRow,

        showDivider && {

          borderTopWidth: 1,

          borderTopColor:

            t.border,

        },

      ]}

    >

      <Pressable

        onPress={onComplete}

        accessibilityLabel={`Complete ${task.title}`}

        style={({ pressed }) => [

          styles.checkbox,

          {

            backgroundColor:

              t.surface2,

            borderColor:

              t.border,

          },

          pressed &&

            styles.pressed,

        ]}

      >

        <Check

          size={11}

          color={t.muted}

        />

      </Pressable>





      <Pressable

        onPress={onOpen}

        style={({ pressed }) => [

          styles.taskOpenButton,

          pressed &&

            styles.pressed,

        ]}

      >

        <View

          style={

            styles.taskTextContainer

          }

        >

          <Text

            numberOfLines={1}

            style={[

              styles.taskTitle,

              {

                color:

                  t.text,

              },

            ]}

          >

            {task.title}

          </Text>



          <Text

            style={[

              styles.taskSection,

              {

                color:

                  t.muted,

              },

            ]}

          >

            {recurrenceLabel(task)
              ? `${task.section} · ${recurrenceLabel(task)}`
              : task.section}

          </Text>

        </View>



        <ChevronRight

          size={14}

          color={t.muted}

        />

      </Pressable>

    </View>

  )

}





// ============================================================

// STYLES

// ============================================================



const styles = StyleSheet.create({

  container: {

    flex: 1,

  },



  safeArea: {

    flex: 1,

  },



  scrollContent: {

    paddingHorizontal: 20,

    paddingTop: 8,

  },





  // ==========================================================

  // HEADER

  // ==========================================================



  header: {

    flexDirection: 'row',

    alignItems: 'flex-start',

    justifyContent:

      'space-between',

    marginBottom: 16,

  },



  headerTextContainer: {

    flex: 1,

  },



  greeting: {

    fontSize: 21,

    fontWeight: '700',

    fontFamily:

      'DM Serif Display',

  },



  date: {

    fontSize: 11.5,

    marginTop: 2,

    fontFamily: 'Outfit',

  },



  profileButton: {

    width: 36,

    height: 36,

    borderRadius: 18,

    alignItems: 'center',

    justifyContent:

      'center',

    borderWidth: 1,

  },





  // ==========================================================

  // DAILY DIGEST

  // ==========================================================



  digestCard: {

    width: '100%',

    minHeight: 62,

    flexDirection: 'row',

    alignItems: 'center',

    justifyContent:

      'space-between',

    paddingHorizontal: 16,

    paddingVertical: 14,

    borderRadius: 16,

    borderWidth: 1,

    marginBottom: 16,

  },



  digestContent: {

    flexDirection: 'row',

    alignItems: 'center',

  },



  digestItem: {

    flexDirection: 'row',

    alignItems: 'center',

  },



  statusDot: {

    width: 8,

    height: 8,

    borderRadius: 4,

    marginRight: 6,

  },



  digestText: {

    fontSize: 13,

    fontWeight: '500',

    fontFamily: 'Outfit',

  },



  digestNumber: {

    fontWeight: '700',

  },



  digestDivider: {

    width: 1,

    height: 16,

    marginHorizontal: 16,

  },





  // ==========================================================

  // EMPTY

  // ==========================================================



  emptyCard: {

    borderRadius: 18,

    borderWidth: 1,

    padding: 24,

    alignItems: 'center',

    marginBottom: 16,

  },



  emptyTitle: {

    fontSize: 16,

    fontWeight: '600',

    marginTop: 10,

    fontFamily: 'Outfit',

  },



  emptySubtitle: {

    fontSize: 12,

    textAlign: 'center',

    lineHeight: 18,

    marginTop: 5,

    marginBottom: 14,

    fontFamily: 'Outfit',

  },



  emptyButton: {

    borderRadius: 999,

    paddingHorizontal: 18,

    paddingVertical: 11,

  },



  emptyButtonText: {

    color: '#FFFFFF',

    fontSize: 12.5,

    fontWeight: '600',

    fontFamily: 'Outfit',

  },





  // ==========================================================

  // SECTION

  // ==========================================================



  section: {

    marginBottom: 16,

  },



  sectionHeader: {

    flexDirection: 'row',

    alignItems: 'center',

    justifyContent:

      'space-between',

    marginBottom: 7,

  },



  sectionTitleRow: {

    flexDirection: 'row',

    alignItems: 'center',

    gap: 6,

  },



  sectionTitle: {

    fontSize: 14.5,

    fontFamily:

      'DM Serif Display',

  },



  taskCount: {

    fontSize: 10.5,

    fontFamily: 'Outfit',

  },





  // ==========================================================

  // SUGGESTED

  // ==========================================================



  suggestedCard: {

    width: '100%',

    padding: 14,

    borderRadius: 17,

    borderWidth: 1.5,

  },



  suggestedTopRow: {

    flexDirection: 'row',

    alignItems: 'center',

    justifyContent:

      'space-between',

    marginBottom: 9,

  },



  reasonBadge: {

    borderRadius: 999,

    paddingHorizontal: 9,

    paddingVertical: 4,

  },



  reasonText: {

    fontSize: 10.5,

    fontWeight: '600',

    fontFamily: 'Outfit',

  },



  sectionName: {

    fontSize: 10.5,

    textTransform:

      'capitalize',

    fontFamily: 'Outfit',

  },



  suggestedTaskButton: {

    width: '100%',

  },



  suggestedTitle: {

    fontSize: 17,

    lineHeight: 22,

    fontWeight: '600',

    fontFamily: 'Outfit',

  },



  suggestedDeadline: {

    fontSize: 11.5,

    marginTop: 5,

    fontFamily: 'Outfit',

  },





  // ==========================================================

  // ACTIONS

  // ==========================================================



  actionRow: {

    flexDirection: 'row',

    gap: 8,

    marginTop: 13,

  },



  primaryAction: {

    flex: 1,

    minHeight: 38,

    borderRadius: 10,

    flexDirection: 'row',

    alignItems: 'center',

    justifyContent:

      'center',

    gap: 6,

  },



  primaryActionText: {

    color: '#FFFFFF',

    fontSize: 11.5,

    fontWeight: '600',

    fontFamily: 'Outfit',

  },



  secondaryAction: {

    flex: 1,

    minHeight: 38,

    borderRadius: 10,

    borderWidth: 1,

    alignItems: 'center',

    justifyContent:

      'center',

  },



  secondaryActionText: {

    fontSize: 11.5,

    fontWeight: '500',

    fontFamily: 'Outfit',

  },





  // ==========================================================

  // ENERGY

  // ==========================================================



  energyRow: {

    flexDirection: 'row',

    gap: 6,

    marginTop: 9,

  },



  energyChip: {

    flex: 1,

    borderRadius: 999,

    borderWidth: 1,

    paddingVertical: 7,

    alignItems: 'center',

    justifyContent:

      'center',

  },



  energyText: {

    fontSize: 10,

    fontWeight: '500',

    fontFamily: 'Outfit',

  },





  // ==========================================================

  // OVERDUE

  // ==========================================================



  overdueBadge: {

    borderRadius: 999,

    paddingHorizontal: 8,

    paddingVertical: 4,

  },



  overdueBadgeText: {

    fontSize: 10,

    fontWeight: '600',

    fontFamily: 'Outfit',

  },



  overdueRow: {

    flexDirection: 'row',

    alignItems: 'center',

    gap: 7,

    padding: 10,

    borderRadius: 17,

    borderWidth: 1,

  },



  overdueTaskButton: {

    flex: 1,

    minWidth: 0,

  },



  overdueTitle: {

    fontSize: 12.5,

    fontWeight: '600',

    fontFamily: 'Outfit',

  },



  overdueSubtitle: {

    fontSize: 9.5,

    marginTop: 2,

    fontFamily: 'Outfit',

  },



  rescheduleButton: {

    borderRadius: 9,

    paddingHorizontal: 10,

    paddingVertical: 7,

  },



  rescheduleText: {

    fontSize: 10,

    fontWeight: '600',

    fontFamily: 'Outfit',

  },



  completeSmallButton: {

    width: 30,

    height: 30,

    borderRadius: 9,

    alignItems: 'center',

    justifyContent:

      'center',

  },





  // ==========================================================

  // TASK LIST

  // ==========================================================



  taskList: {

    overflow: 'hidden',

    borderRadius: 17,

    borderWidth: 1,

  },



  taskRow: {

    flexDirection: 'row',

    alignItems: 'center',

    gap: 10,

    paddingHorizontal: 12,

    paddingVertical: 10,

  },



  checkbox: {

    width: 25,

    height: 25,

    borderRadius: 13,

    borderWidth: 1.5,

    alignItems: 'center',

    justifyContent:

      'center',

  },



  taskOpenButton: {

    flex: 1,

    minWidth: 0,

    flexDirection: 'row',

    alignItems: 'center',

  },



  taskTextContainer: {

    flex: 1,

    minWidth: 0,

  },



  taskTitle: {

    fontSize: 12.5,

    fontWeight: '500',

    fontFamily: 'Outfit',

  },



  taskSection: {

    fontSize: 9.5,

    textTransform:

      'capitalize',

    marginTop: 1,

    fontFamily: 'Outfit',

  },





  // ==========================================================

  // PRESS

  // ==========================================================



  pressed: {

    opacity: 0.7,

  },

})
