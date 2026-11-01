import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useRef,
  type ReactNode,
} from 'react'

import type {
  Task,
  AppContextType,
  TaskStore,
  TaskUpdates,
  EnergyLevel,
} from '../types'

import { lightTheme, darkTheme } from '../theme'
import { supabase } from '../lib/supabase'
import { apiFetch } from '@/lib/apiClient'

const AppContext = createContext<AppContextType | null>(null)

interface AppProviderProps {
  children: ReactNode
}

// -----------------------------
// Helpers
// -----------------------------
const SECTIONS = ['work', 'personal', 'leisure']

type Row = Record<string, any>

// The UI offers "focused"; the backend only knows low | medium | high.
const toBackendEnergy = (value: EnergyLevel): string | null =>
  value === 'focused' ? 'medium' : value

function mapRow(
  row: Row,
  dueIds: Set<string>,
  riskIds: Set<string>
): Task | null {
  // Older agent-created rows can have a null section. Default those to
  // Personal so they remain reachable from the section list and editable.
  const section = SECTIONS.includes(row.section)
    ? row.section as Task['section']
    : 'personal'

  return {
    id: row.id,
    title: row.title,
    section,

    brief: row.brief ?? undefined,

    // Keep original ISO timestamp.
    deadline: row.deadline ?? null,

    priority: 'medium',

    priorityScore: row.priority_score ?? undefined,

    priorityWhy: row.explanation ?? undefined,

    // The dashboard endpoint never sends estimated_time_minutes,
    // so this stays undefined (estimates are backend-only).
    estimatedTime:
      row.estimated_time_minutes != null
        ? String(row.estimated_time_minutes)
        : undefined,

    // Decided by the backend, not guessed on the client.
    dueToday: dueIds.has(row.id),
    atRisk: riskIds.has(row.id),

    effort: row.effort ?? undefined,
    urgency: row.urgency ?? undefined,
    scheduleType: row.schedule_type ?? undefined,
    scheduledStart: row.scheduled_start ?? undefined,
    scheduledEnd: row.scheduled_end ?? undefined,
    hasExplicitTime: row.has_explicit_time ?? undefined,
    isBlocked: row.is_blocked ?? false,
    blocked: row.is_blocked ?? false,
    isRecurring: row.is_recurring ?? undefined,
    recurrence: row.recurrence ?? undefined,
    recurrenceEnd: row.recurrence_end ?? undefined,
    isOverdue: Boolean(row.is_overdue),

    // pinned | deadline_risk | energy_match | top_score
    reason: row.reason ?? undefined,
  }
}

const EMPTY_STORE: TaskStore = {
  work: [],
  personal: [],
  leisure: [],
}

const API_UPDATE_FIELD: Record<keyof TaskUpdates, string> = {
  title: 'title',
  brief: 'brief',
  effort: 'effort',
  urgency: 'urgency',
  deadline: 'deadline',
  scheduleType: 'schedule_type',
  scheduledStart: 'scheduled_start',
  scheduledEnd: 'scheduled_end',
  hasExplicitTime: 'has_explicit_time',
  isBlocked: 'is_blocked',
  isRecurring: 'is_recurring',
  recurrence: 'recurrence',
  recurrenceEnd: 'recurrence_end',
}

function taskUpdatesToApi(updates: TaskUpdates) {
  return Object.fromEntries(
    Object.entries(updates).map(([key, value]) => [
      API_UPDATE_FIELD[key as keyof TaskUpdates] ?? key,
      value,
    ]),
  )
}

export function AppProvider({ children }: AppProviderProps) {
  // -----------------------------
  // Dark mode
  // -----------------------------
  const [darkMode, setDarkMode] = useState(false)

  const toggleDark = () => setDarkMode((prev) => !prev)

  // -----------------------------
  // Tasks (every non-completed task, grouped by section)
  // Order inside a section: overdue, recommended (backend order), later
  // -----------------------------
  const [tasks, setTasks] = useState<TaskStore>(EMPTY_STORE)

  // Lists straight from the backend, already ordered
  const [rankedTasks, setRankedTasks] = useState<Task[]>([])
  const [overdueTasks, setOverdueTasks] = useState<Task[]>([])
  const [suggestedList, setSuggestedList] = useState<Task[]>([])
  const [dueTodayTasks, setDueTodayTasks] = useState<Task[]>([])
  const [scheduledTodayTasks, setScheduledTodayTasks] = useState<Task[]>([])
  const [atRiskTasks, setAtRiskTasks] = useState<Task[]>([])

  // -----------------------------
  // Energy
  // -----------------------------
  const [energy, setEnergy] = useState<EnergyLevel>(null)

  // fetchTasks is called from long-lived callbacks, so it reads the
  // latest energy from a ref instead of a stale closure.
  const energyRef = useRef<EnergyLevel>(null)
  energyRef.current = energy

  // Used to ignore responses of older, slower requests.
  const requestId = useRef(0)
  const sessionGeneration = useRef(0)
  const activeUserId = useRef<string | null>(null)
  const taskRequest = useRef<AbortController | null>(null)
  const historyRequest = useRef<AbortController | null>(null)
  const profileRequest = useRef<AbortController | null>(null)

  const cancelAccountLoads = () => {
    sessionGeneration.current += 1
    requestId.current += 1
    taskRequest.current?.abort()
    historyRequest.current?.abort()
    profileRequest.current?.abort()
    taskRequest.current = null
    historyRequest.current = null
    profileRequest.current = null
  }

  // -----------------------------
  // Suggested task
  // Backend is the source of truth
  // -----------------------------
  const [suggestedTask, setSuggestedTask] = useState<Task | null>(null)

  const resetTasks = () => {
    setTasks(EMPTY_STORE)
    setRankedTasks([])
    setOverdueTasks([])
    setSuggestedList([])
    setSuggestedTask(null)
    setDueTodayTasks([])
    setScheduledTodayTasks([])
    setAtRiskTasks([])
  }

  // -----------------------------
  // Fetch tasks: ONE backend call
  // -----------------------------
  const fetchTasks = async () => {
    const myRequest = ++requestId.current
    const myGeneration = sessionGeneration.current
    taskRequest.current?.abort()
    const controller = new AbortController()
    taskRequest.current = controller

    let authUser
    try {
      const result = await supabase.auth.getUser()
      authUser = result.data.user
    } catch (error) {
      if (!controller.signal.aborted) console.error('Error checking dashboard user:', error)
      return
    }

    if (myGeneration !== sessionGeneration.current || controller.signal.aborted) return

    if (!authUser) {
      if (myGeneration === sessionGeneration.current) resetTasks()
      return
    }

    let d: Row

    try {
      const backendEnergy = toBackendEnergy(energyRef.current)

      const query = backendEnergy
        ? `?energy=${encodeURIComponent(backendEnergy)}`
        : ''

      d = await apiFetch(`/tasks/dashboard${query}`, { signal: controller.signal })

    } catch (error) {
      if (!controller.signal.aborted) console.error('Error fetching dashboard:', error)
      return
    }

    // A newer request started while this one was running.
    if (myRequest !== requestId.current || myGeneration !== sessionGeneration.current || controller.signal.aborted) return

    const idsOf = (rows?: Row[]) =>
      new Set<string>((rows ?? []).map((r) => r.id))

    const dueIds = idsOf(d.due_today)
    const riskIds = idsOf(d.at_risk)

    const toTasks = (rows?: Row[]): Task[] =>
      (rows ?? [])
        .map((r) => mapRow(r, dueIds, riskIds))
        .filter((task): task is Task => task !== null)

    const ranked = toTasks(d.ranked)
    const overdue = toTasks((d.overdue ?? []).map((row: Row) => ({ ...row, is_overdue: true })))
    const later = toTasks(d.later)
    const upcoming = toTasks(d.upcoming)
    const suggested = toTasks(d.suggested)

    const grouped: TaskStore = {
      work: [],
      personal: [],
      leisure: [],
    }

    // Backend order is preserved inside every section.
    const seen = new Set<string>()

;[...overdue, ...ranked, ...upcoming, ...later].forEach((task) => {
  if (seen.has(task.id)) return

  seen.add(task.id)
  grouped[task.section].push(task)
})

    setTasks(grouped)
    setRankedTasks(ranked)
    setOverdueTasks(overdue)
    setSuggestedList(suggested)
    setSuggestedTask(suggested[0] ?? null)
    setDueTodayTasks(toTasks(d.due_today))
    setScheduledTodayTasks(toTasks(d.scheduled_today ?? []))
    setAtRiskTasks(toTasks(d.at_risk))
  }

  // -----------------------------
  // History
  // -----------------------------
  const [history, setHistory] =
    useState<
      AppContextType['history']
    >([])

  const fetchHistory = async () => {
    const myGeneration = sessionGeneration.current
    historyRequest.current?.abort()
    const controller = new AbortController()
    historyRequest.current = controller
    const { data: { user: authUser } } = await supabase.auth.getUser()

    if (myGeneration !== sessionGeneration.current || controller.signal.aborted) return

    if (!authUser) {
      if (myGeneration === sessionGeneration.current) setHistory([])
      return
    }

    const { data, error } = await supabase
      .from('tasks')
      .select(
        'id, title, section, status, completed_at'
      )
      .eq('user_id', authUser.id)
      .eq('status', 'completed')
      .abortSignal(controller.signal)
      .order('completed_at', {
        ascending: false,
      })

    if (error) {
      if (controller.signal.aborted || myGeneration !== sessionGeneration.current) return
      console.error(
        'Error fetching history:',
        error
      )
      return
    }

    const completedHistory =
      (data ?? []).map((row) => ({
        id: row.id,
        title: row.title,
        section: row.section ?? null,
        type: 'completed' as const,
        date: row.completed_at
          ? new Date(
              row.completed_at
            ).toLocaleDateString(
              'en-US',
              {
                month: 'short',
                day: 'numeric',
                year: 'numeric',
              }
            )
          : '',
      }))

    if (!controller.signal.aborted && myGeneration === sessionGeneration.current) setHistory(completedHistory)
  }

  // -----------------------------
  // User
  // -----------------------------
  const [user, setUser] =
    useState({
      name: '',
      email: '',
      profession: '',
    })

  const loadUser = async () => {
    const myGeneration = sessionGeneration.current
    profileRequest.current?.abort()
    const controller = new AbortController()
    profileRequest.current = controller
    const {
      data: { user: authUser },
    } = await supabase.auth.getUser()

    if (myGeneration !== sessionGeneration.current || controller.signal.aborted) return

    if (!authUser) {
      if (myGeneration === sessionGeneration.current) setUser({
        name: '',
        email: '',
        profession: '',
      })
      return
    }

    const { data: profile } =
      await supabase
        .from('user_profile')
        .select('name, profession')
        .eq('user_id', authUser.id)
        .abortSignal(controller.signal)
        .single()

    if (controller.signal.aborted || myGeneration !== sessionGeneration.current) return
    setUser({
      name: profile?.name ?? '',
      email: authUser.email ?? '',
      profession:
        profile?.profession ?? '',
    })
  }

  // -----------------------------
  // History / user / auth changes
  // -----------------------------
  useEffect(() => {
    fetchHistory()
    loadUser()

    const {
      data: listener,
    } =
      supabase.auth.onAuthStateChange(
        (_event, session) => {
          const nextUserId = session?.user.id ?? null
          if (nextUserId !== activeUserId.current) {
            cancelAccountLoads()
            activeUserId.current = nextUserId
          }
          if (session) {
            fetchTasks()
            fetchHistory()
            loadUser()
          } else {
            resetTasks()

            setHistory([])

            setUser({
              name: '',
              email: '',
              profession: '',
            })
          }
        }
      )

    return () => {
      listener.subscription.unsubscribe()
      cancelAccountLoads()
    }
  }, [])

  // -----------------------------
  // Fetch on mount, and again whenever the energy
  // chip changes (including when it is cleared).
  // -----------------------------
  useEffect(() => {
    fetchTasks()
  }, [energy])

  // -----------------------------
  // Complete task
  // -----------------------------
  const completeTask = async (
    id: string
  ) => {
    const allTasks = [
      ...tasks.work,
      ...tasks.personal,
      ...tasks.leisure,
    ]

    const task = allTasks.find(
      (task) => task.id === id
    )

    if (!task) return

    await apiFetch(`/tasks/${encodeURIComponent(id)}/complete`, {
      method: 'POST',
    })

    const today =
      new Date().toLocaleDateString(
        'en-US',
        {
          month: 'short',
          day: 'numeric',
          year: 'numeric',
        }
      )

    setHistory((prev) => [
      {
        id: task.id,
        title: task.title,
        section: task.section,
        type: 'completed',
        date: today,
      },
      ...prev,
    ])

    // Instant feedback; the refetch below corrects anything else.
    const without = (list: Task[]) =>
      list.filter((item) => item.id !== id)

    setTasks((prev) => ({
      work: without(prev.work),
      personal: without(prev.personal),
      leisure: without(prev.leisure),
    }))
    setRankedTasks(without)
    setOverdueTasks(without)
    setSuggestedList(without)
    setDueTodayTasks(without)
    setAtRiskTasks(without)
    setSuggestedTask((prev) =>
      prev?.id === id ? null : prev
    )

    // Get the next backend recommendation.
    await fetchTasks()
  }

  // -----------------------------
  // Add task
  // NOTE: tasks are now created only through the chat agent.
  // Remove this once nothing calls it (it bypasses the AI parser).
  // -----------------------------
  const addTask = async (
    task: Task
  ) => {
    const durationEstimate = task.estimatedTime
      ? Number.parseInt(task.estimatedTime, 10)
      : null
    await apiFetch('/tasks', {
      method: 'POST',
      body: JSON.stringify({
        title: task.title,
        section: task.section,
        brief: task.brief ?? null,
        schedule_type: task.scheduleType ?? 'flexible',
        deadline: task.deadline ?? null,
        scheduled_start: task.scheduledStart ?? null,
        scheduled_end: task.scheduledEnd ?? null,
        has_explicit_time: task.hasExplicitTime ?? false,
        is_recurring: task.isRecurring ?? false,
        recurrence: task.recurrence ?? null,
        recurrence_end: task.recurrenceEnd ?? null,
        duration: null,
        estimated_time_minutes:
          durationEstimate != null && Number.isFinite(durationEstimate)
            ? durationEstimate
            : null,
        is_blocked: task.isBlocked ?? false,
        effort: task.effort ?? null,
        urgency: task.urgency ?? null,
        source_type: 'text',
      }),
    })

    await fetchTasks()
  }

  // -----------------------------
  // Update task information
  // -----------------------------
  const updateTask = async (
    id: string,
    section:
      | 'work'
      | 'personal'
      | 'leisure',
    updates: TaskUpdates
  ) => {
    await apiFetch(`/tasks/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify({
        ...taskUpdatesToApi(updates),
        section,
      }),
    })

    // Re-fetch after update because
    // deadline / time can change ranking.
    await fetchTasks()
  }

  const deleteTask = async (id: string, _section: Task['section']) => {
    await apiFetch(`/tasks/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    })
    await fetchTasks()
  }

  // -----------------------------
  // Refresh everything
  // -----------------------------
  const refreshTasks = async () => {
    await fetchTasks()
    await fetchHistory()
  }

  // -----------------------------
  // Theme
  // -----------------------------
  const t = darkMode
    ? darkTheme
    : lightTheme

  // -----------------------------
  // Counts come from the backend lists
  // -----------------------------
  const dueTodayCount = dueTodayTasks.length
  const atRiskCount = atRiskTasks.length
  const overdueCount = overdueTasks.length

  // -----------------------------
  // Context value
  // -----------------------------
  const value: AppContextType = {
    darkMode,

    toggleDark,

    t,

    tasks,

    completeTask,

    addTask,

    updateTask,

    deleteTask,

    energy,

    setEnergy,

    refreshTasks,

    user,

    dueTodayCount,

    atRiskCount,

    overdueCount,

    suggestedTask,

    suggestedList,

    rankedTasks,

    overdueTasks,

    dueTodayTasks,

    scheduledTodayTasks,

    atRiskTasks,

    history,
  }

  return (
    <AppContext.Provider
      value={value}
    >
      {children}
    </AppContext.Provider>
  )
}

// -----------------------------
// useApp hook
// -----------------------------
export function useApp(): AppContextType {
  const context =
    useContext(AppContext)

  if (!context) {
    throw new Error(
      'useApp must be used inside AppProvider'
    )
  }

  return context
}
