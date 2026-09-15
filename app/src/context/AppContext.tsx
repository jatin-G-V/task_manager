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
import { initialTasks, initialHistory } from '../data'
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
  const [tasks, setTasks] = useState<TaskStore>(initialTasks)

  const completeTask = (id: string) => {
    const allTasks = [...tasks.work, ...tasks.personal, ...tasks.leisure]
    const task = allTasks.find((task) => task.id === id)

    if (task) {
      const today = new Date().toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      })
      setHistory((prev) => [
        { id: `h${Date.now()}`, title: task.title, section: task.section, type: 'completed', date: today },
        ...prev,
      ])
    }

    setTasks((prev) => ({
      work: prev.work.filter((task) => task.id !== id),
      personal: prev.personal.filter((task) => task.id !== id),
      leisure: prev.leisure.filter((task) => task.id !== id),
    }))
  }

  const addTask = (task: Task) => {
    setTasks((prev) => ({
      ...prev,
      [task.section]: [...prev[task.section], task],
    }))
  }

  // -----------------------------
  // Energy
  // -----------------------------
  const [energy, setEnergy] = useState<EnergyLevel>(null)

  // -----------------------------
  // History
  // -----------------------------
  const [history, setHistory] = useState(initialHistory)

  // -----------------------------
  // User (real, from Supabase — replaces mockUser)
  // -----------------------------
  const [user, setUser] = useState({ name: '', email: '', profession: '' })

  useEffect(() => {
    async function loadUser() {
      const { data: { user: authUser } } = await supabase.auth.getUser()
      if (!authUser) return

      const { data: profile } = await supabase
        .from('user_profile')
        .select('name, profession')
        .eq('user_id', authUser.id)
        .single()

      setUser({
        name: profile?.name ?? '',
        email: authUser.email ?? '',
        profession: profile?.profession ?? '',
      })
    }
    loadUser()
  }, [])

  // -----------------------------
  // Theme
  // -----------------------------
  const t = darkMode ? darkTheme : lightTheme

  // -----------------------------
  // Derived task information
  // -----------------------------
  const allTasks = [...tasks.work, ...tasks.personal, ...tasks.leisure]
  const dueTodayCount = allTasks.filter((task) => task.dueToday).length
  const atRiskCount = allTasks.filter((task) => task.atRisk).length
  const suggestedTask = tasks.work[0] ?? tasks.personal[0] ?? null

  // -----------------------------
  // Context
  // -----------------------------
  const value: AppContextType = {
    darkMode,
    toggleDark,
    t,
    tasks,
    completeTask,
    addTask,
    energy,
    setEnergy,
    user,
    dueTodayCount,
    atRiskCount,
    suggestedTask,
    history,
  }

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

// -----------------------------
// Hook
// -----------------------------
export function useApp(): AppContextType {
  const context = useContext(AppContext)
  if (!context) {
    throw new Error('useApp must be used inside AppProvider')
  }
  return context
}