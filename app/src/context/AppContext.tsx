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
import { apiFetch } from '@/lib/apiClient'

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
  // Energy
  // -----------------------------
  const [energy, setEnergy] =
    useState<EnergyLevel>(null)

  // -----------------------------
  // Suggested task
  // Backend is the source of truth
  // -----------------------------
  const [suggestedTask, setSuggestedTask] =
    useState<Task | null>(null)

  // -----------------------------
  // Fetch tasks
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

      setSuggestedTask(null)

      return
    }

    // ---------------------------------
    // 1. Fetch actual task data
    //    from Supabase
    // ---------------------------------
    const { data, error } = await supabase
      .from('tasks')
      .select('*')
      .eq('user_id', authUser.id)
      .neq('status', 'completed')
      .order('created_at', { ascending: false })

    if (error) {
      console.error(
        'Error fetching tasks:',
        error
      )
      return
    }

    // ---------------------------------
    // 2. Convert Supabase rows
    //    into frontend Task objects
    // ---------------------------------
    const allMappedTasks: Task[] = []

    data?.forEach((row) => {
      if (
        ![
          'work',
          'personal',
          'leisure',
        ].includes(row.section)
      ) {
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

        brief:
          row.brief ?? undefined,

        // Keep original ISO timestamp.
        deadline:
          row.deadline ?? '',

        priority: 'medium',

        priorityScore:
          row.priority_score ?? undefined,

        priorityWhy:
          row.explanation ?? undefined,

        // Keep only numeric value.
        // Example: "45", not "45 min".
        estimatedTime:
          row.estimated_time_minutes != null
            ? String(
                row.estimated_time_minutes
              )
            : undefined,

        blocked:
          row.is_blocked ?? false,

        dueToday: row.deadline
          ? new Date(
              row.deadline
            ).toDateString() ===
            new Date().toDateString()
          : false,

        atRisk:
          row.is_blocked === true,
      }

      allMappedTasks.push(task)
    })

    // ---------------------------------
    // 3. Create backend ranking
    // ---------------------------------
    let ranked: { id: string }[] = []

    try {
      const energyQuery = energy
        ? `&energy=${encodeURIComponent(energy)}`
        : ''

      const response = await apiFetch(
        `/tasks/recommended?limit=100${energyQuery}`
      )

      if (Array.isArray(response)) {
        ranked = response
      } else {
        console.warn(
          'Recommended tasks response is not an array:',
          response
        )
      }
    } catch (error) {
      console.error(
        'Error fetching recommended tasks:',
        error
      )
    }

    // ---------------------------------
    // 4. Build backend rank index
    // ---------------------------------
    const rankIndex = new Map<
      string,
      number
    >(
      ranked.map(
        (
          item: { id: string },
          index: number
        ) => [item.id, index]
      )
    )

    // ---------------------------------
    // 5. Sort ONLY according to backend
    // ---------------------------------
    const sortByBackendRank = (
      a: Task,
      b: Task
    ) =>
      (rankIndex.get(a.id) ??
        Number.MAX_SAFE_INTEGER) -
      (rankIndex.get(b.id) ??
        Number.MAX_SAFE_INTEGER)

    // ---------------------------------
    // 6. Group tasks while preserving
    //    backend ranking
    // ---------------------------------
    const groupedTasks: TaskStore = {
      work: [],
      personal: [],
      leisure: [],
    }

    allMappedTasks.forEach((task) => {
      groupedTasks[task.section].push(task)
    })

    groupedTasks.work.sort(
      sortByBackendRank
    )

    groupedTasks.personal.sort(
      sortByBackendRank
    )

    groupedTasks.leisure.sort(
      sortByBackendRank
    )

    // ---------------------------------
    // 7. Update task store
    // ---------------------------------
    setTasks(groupedTasks)

    // ---------------------------------
    // 8. First backend-ranked task
    //    becomes Suggested Focus
    // ---------------------------------
    if (ranked.length > 0) {
      const firstRecommendedTask =
        allMappedTasks.find(
          (task) =>
            task.id === ranked[0].id
        ) ?? null

      setSuggestedTask(
        firstRecommendedTask
      )
    } else {
      setSuggestedTask(null)
    }
  }

  // -----------------------------
  // History
  // -----------------------------
  const [history, setHistory] =
    useState<
      AppContextType['history']
    >([])

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
      .select(
        'id, title, section, status, completed_at'
      )
      .eq('user_id', authUser.id)
      .eq('status', 'completed')
      .order('completed_at', {
        ascending: false,
      })

    if (error) {
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
        section: row.section,
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

    setHistory(completedHistory)
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
    const {
      data: { user: authUser },
    } = await supabase.auth.getUser()

    if (!authUser) {
      setUser({
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
        .single()

    setUser({
      name: profile?.name ?? '',
      email: authUser.email ?? '',
      profession:
        profile?.profession ?? '',
    })
  }

  // -----------------------------
  // Load tasks / user / history
  // -----------------------------
  useEffect(() => {
    fetchTasks()
    fetchHistory()
    loadUser()

    const {
      data: listener,
    } =
      supabase.auth.onAuthStateChange(
        (_event, session) => {
          if (session) {
            fetchTasks()
            fetchHistory()
            loadUser()
          } else {
            setTasks({
              work: [],
              personal: [],
              leisure: [],
            })

            setSuggestedTask(null)

            setHistory([])

            setUser({
              name: '',
              email: '',
              profession: '',
            })
          }
        }
      )

    return () =>
      listener.subscription.unsubscribe()
  }, [])

  // -----------------------------
  // Re-rank when energy changes
  // -----------------------------
  useEffect(() => {
    if (energy !== null) {
      fetchTasks()
    }
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

    const completedAt =
      new Date().toISOString()

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

    // If completed task was Suggested Focus,
    // get the next backend recommendation.
    await fetchTasks()
  }

  // -----------------------------
  // Add task
  // -----------------------------
  const addTask = async (
    task: Task
  ) => {
    const {
      data: { user: authUser },
    } = await supabase.auth.getUser()

    if (!authUser) {
      throw new Error(
        'User is not authenticated'
      )
    }

    const { error } = await supabase
      .from('tasks')
      .insert({
        user_id: authUser.id,

        title: task.title,

        section: task.section,

        brief:
          task.brief ?? null,

        deadline: null,

        estimated_time_minutes:
          null,

        priority_score:
          null,

        explanation:
          null,

        status: 'pending',

        is_blocked: false,

        source_type: 'text',
      })

    if (error) {
      console.error(
        'Error creating task:',
        error
      )
      throw error
    }

    // Re-fetch so backend ranking
    // decides where the new task belongs.
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

    // Re-fetch after update because
    // deadline / estimated time can
    // change backend ranking.
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

  // IMPORTANT:
  // No client-side ranking here.
  // suggestedTask comes directly
  // from backend recommendation.
  // -----------------------------

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

    refreshTasks,

    user,

    dueTodayCount,

    atRiskCount,

    suggestedTask,

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