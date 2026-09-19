import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  type ReactNode,
} from 'react'

import type {
  Task,
  AppContextType,
  TaskStore,
  EnergyLevel,
} from '../types'

import { lightTheme, darkTheme } from '../theme'
import { supabase } from '../lib/supabase'

const AppContext = createContext<AppContextType | null>(null)

interface AppProviderProps {
  children: ReactNode
}

export function AppProvider({ children }: AppProviderProps) {
  // -----------------------------
  // Dark mode
  // -----------------------------
  const [darkMode, setDarkMode] = useState(false)

  const toggleDark = () => setDarkMode((prev) => !prev)

  // -----------------------------
  // Tasks
  // -----------------------------
  const [tasks, setTasks] = useState<TaskStore>({
    work: [],
    personal: [],
    leisure: [],
  })

  // -----------------------------
  // Fetch tasks from Supabase
  // -----------------------------
  const fetchTasks = async () => {
    const {
      data: { user: authUser },
    } = await supabase.auth.getUser()

    if (!authUser) {
      setTasks({
        work: [],
        personal: [],
        leisure: [],
      })
      return
    }

    const { data, error } = await supabase
  .from('tasks')
  .select('*')
  .eq('user_id', authUser.id)
  .neq('status', 'completed')
  .order('created_at', { ascending: false })

    if (error) {
      console.error('Error fetching tasks:', error)
      return
    }

    const groupedTasks: TaskStore = {
      work: [],
      personal: [],
      leisure: [],
    }

    data?.forEach((row) => {
      if (!['work', 'personal', 'leisure'].includes(row.section)) {
        return
      }

      const section = row.section as
        | 'work'
        | 'personal'
        | 'leisure'

      const task: Task = {
        id: row.id,
        title: row.title,
        section,

        brief: row.brief ?? undefined,

        // Keep the original ISO timestamp from Supabase.
        // Do not convert it to a display date here.
        deadline: row.deadline ?? '',

        priority: 'medium',

        priorityScore:
          row.priority_score ?? undefined,

        priorityWhy:
          row.explanation ?? undefined,

        // Keep only the numeric value here.
        // The UI will add "min" when displaying it.
        estimatedTime:
          row.estimated_time_minutes != null
            ? String(row.estimated_time_minutes)
            : undefined,

        blocked:
          row.is_blocked ?? false,

        dueToday: row.deadline
          ? new Date(row.deadline).toDateString() ===
            new Date().toDateString()
          : false,

        atRisk:
          row.is_blocked === true,
      }

      groupedTasks[section].push(task)
    })

    setTasks(groupedTasks)
  }

  // -----------------------------
  // Load tasks once on app start
  // -----------------------------
  useEffect(() => {
  fetchTasks()
  fetchHistory()
}, [])

  // -----------------------------
  // Complete task
  // -----------------------------
const completeTask = async (id: string) => {
  const allTasks = [
    ...tasks.work,
    ...tasks.personal,
    ...tasks.leisure,
  ]

  const task = allTasks.find(
    (task) => task.id === id
  )

  if (!task) return

  const completedAt = new Date().toISOString()

  const { error } = await supabase
    .from('tasks')
    .update({
      status: 'completed',
      completed_at: completedAt,
    })
    .eq('id', id)

  if (error) {
    console.error(
      'Error completing task:',
      error
    )
    throw error
  }

  const today = new Date().toLocaleDateString(
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

  setTasks((prev) => ({
    work: prev.work.filter(
      (task) => task.id !== id
    ),
    personal: prev.personal.filter(
      (task) => task.id !== id
    ),
    leisure: prev.leisure.filter(
      (task) => task.id !== id
    ),
  }))
}

  // -----------------------------
  // Add task
  // -----------------------------
  const addTask = async (task: Task) => {
    const {
      data: { user: authUser },
    } = await supabase.auth.getUser()

    if (!authUser) {
      throw new Error('User is not authenticated')
    }

    const { data, error } = await supabase
      .from('tasks')
      .insert({
        user_id: authUser.id,
        title: task.title,
        section: task.section,
        brief: task.brief ?? null,

        deadline: null,
        estimated_time_minutes: null,
        priority_score: null,
        explanation: null,

        status: 'pending',
        is_blocked: false,
        source_type: 'text',
      })
      .select()
      .single()

    if (error) {
      console.error(
        'Error creating task:',
        error
      )
      throw error
    }

    const savedTask: Task = {
      ...task,
      id: data.id,
    }

    setTasks((prev) => ({
      ...prev,
      [savedTask.section]: [
        savedTask,
        ...prev[savedTask.section],
      ],
    }))
  }

  // -----------------------------
  // Energy
  // -----------------------------
  const [energy, setEnergy] =
    useState<EnergyLevel>(null)

  // -----------------------------
  // History
  // -----------------------------
  const [history, setHistory] =
  useState<AppContextType['history']>([])

  const fetchHistory = async () => {
    const {
      data: { user: authUser },
    } = await supabase.auth.getUser()

    if (!authUser) {
      setHistory([])
      return
    }

    const { data, error } = await supabase
      .from('tasks')
      .select('id, title, section, status, completed_at')
      .eq('user_id', authUser.id)
      .eq('status', 'completed')
      .order('completed_at', { ascending: false })

    if (error) {
      console.error('Error fetching history:', error)
      return
    }

    const completedHistory = (data ?? []).map((row) => ({
      id: row.id,
      title: row.title,
      section: row.section,
      type: 'completed' as const,
      date: row.completed_at
        ? new Date(row.completed_at).toLocaleDateString(
            'en-US',
            {
              month: 'short',
              day: 'numeric',
              year: 'numeric',
            }
          )
        : '',
  }))

  setHistory(completedHistory)
}

  // -----------------------------
  // User
  // -----------------------------
  const [user, setUser] = useState({
    name: '',
    email: '',
    profession: '',
  })

  useEffect(() => {
    async function loadUser() {
      const {
        data: { user: authUser },
      } = await supabase.auth.getUser()

      if (!authUser) return

      const { data: profile } = await supabase
        .from('user_profile')
        .select('name, profession')
        .eq('user_id', authUser.id)
        .single()

      setUser({
        name: profile?.name ?? '',
        email: authUser.email ?? '',
        profession:
          profile?.profession ?? '',
      })
    }

    loadUser()
  }, [])

  // -----------------------------
  // Theme
  // -----------------------------
  const t = darkMode
    ? darkTheme
    : lightTheme

  // -----------------------------
  // Derived task information
  // -----------------------------
  const allTasks = [
    ...tasks.work,
    ...tasks.personal,
    ...tasks.leisure,
  ]

  const dueTodayCount =
    allTasks.filter(
      (task) => task.dueToday
    ).length

  const atRiskCount =
    allTasks.filter(
      (task) => task.atRisk
    ).length

  const suggestedTask = (() => {
  const allTasks = [...tasks.work, ...tasks.personal, ...tasks.leisure]
  const eligible = allTasks.filter((t) => t.deadline && !t.blocked)

  if (eligible.length === 0) return null

  const now = Date.now()
  const sectionWeight: Record<string, number> = { work: 2, personal: 1, leisure: 1 }

  const scored = eligible.map((t) => {
    const deadlineMs = new Date(t.deadline).getTime()
    const estimatedMinutes = t.estimatedTime ? parseInt(t.estimatedTime, 10) || 0 : 0
    const rawSlack = deadlineMs - now - estimatedMinutes * 60000
    const weightedSlack = rawSlack / sectionWeight[t.section]
    return { task: t, weightedSlack }
  })

  scored.sort((a, b) => a.weightedSlack - b.weightedSlack)
  return scored[0].task
})()

  // -----------------------------
  // Update task information
  // -----------------------------
  const updateTask = async (
    id: string,
    section:
      | 'work'
      | 'personal'
      | 'leisure',
    updates: Partial<{
      title: string
      brief: string | null
      deadline: string | null
      estimated_time_minutes:
        | number
        | null
      status: string
    }>
  ) => {
    const { error } = await supabase
      .from('tasks')
      .update(updates)
      .eq('id', id)

    if (error) {
      console.error(
        'Error updating task:',
        error
      )
      throw error
    }

    setTasks((prev) => ({
      ...prev,

      [section]: prev[section].map((t) =>
        t.id === id
          ? {
              ...t,

              // -----------------------------
              // Title
              // -----------------------------
              title:
                updates.title ?? t.title,

              // -----------------------------
              // Brief
              // -----------------------------
              brief:
                updates.brief !== undefined
                  ? updates.brief ?? undefined
                  : t.brief,

              // -----------------------------
              // Deadline
              // -----------------------------
              // Keep ISO timestamp in state.
              // Do not convert to locale string.
              deadline:
                updates.deadline !== undefined
                  ? updates.deadline ?? ''
                  : t.deadline,

              // -----------------------------
              // Estimated time
              // -----------------------------
              // Keep only the number in state.
              // Example: "50", not "50 min".
              estimatedTime:
                updates.estimated_time_minutes !==
                undefined
                  ? updates.estimated_time_minutes !=
                    null
                    ? String(
                        updates.estimated_time_minutes
                      )
                    : undefined
                  : t.estimatedTime,
            }
          : t
      ),
    }))
  }

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

    energy,
    setEnergy,

    user,

    dueTodayCount,
    atRiskCount,
    suggestedTask,

    history,
  }

  return (
    <AppContext.Provider value={value}>
      {children}
    </AppContext.Provider>
  )
}

// -----------------------------
// useApp hook
// -----------------------------
export function useApp(): AppContextType {
  const context = useContext(AppContext)

  if (!context) {
    throw new Error(
      'useApp must be used inside AppProvider'
    )
  }

  return context
}