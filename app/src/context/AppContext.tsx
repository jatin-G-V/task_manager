import React, {
  createContext,
  useContext,
  useState,
  type ReactNode,
} from 'react'

import type {
  Task,
  AppContextType,
  TaskStore,
  EnergyLevel,
} from '../types'

import { lightTheme, darkTheme } from '../theme'
import {
  initialTasks,
  initialHistory,
  mockUser,
} from '../data'

const AppContext = createContext<AppContextType | null>(null)

interface AppProviderProps {
  children: ReactNode
}

export function AppProvider({ children }: AppProviderProps) {
  // -----------------------------
  // Dark mode
  // -----------------------------

  const [darkMode, setDarkMode] = useState(false)

  const toggleDark = () => {
    setDarkMode((prev) => !prev)
  }

  // -----------------------------
  // Tasks
  // -----------------------------

  const [tasks, setTasks] = useState<TaskStore>(
    initialTasks
  )

  const completeTask = (id: string) => {
    const allTasks = [
      ...tasks.work,
      ...tasks.personal,
      ...tasks.leisure,
    ]

    const task = allTasks.find(
      (task) => task.id === id
    )

    // Add completed task to history
    if (task) {
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
          id: `h${Date.now()}`,
          title: task.title,
          section: task.section,
          type: 'completed',
          date: today,
        },
        ...prev,
      ])
    }

    // Remove task from its section
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

  const addTask = (task: Task) => {
    setTasks((prev) => ({
      ...prev,

      [task.section]: [
        ...prev[task.section],
        task,
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
    useState(initialHistory)

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

  const dueTodayCount = allTasks.filter(
    (task) => task.dueToday
  ).length

  const atRiskCount = allTasks.filter(
    (task) => task.atRisk
  ).length

  const suggestedTask =
    tasks.work[0] ??
    tasks.personal[0] ??
    null

  // -----------------------------
  // Context
  // -----------------------------

  const value: AppContextType = {
    // Theme
    darkMode,
    toggleDark,
    t,

    // Tasks
    tasks,
    completeTask,
    addTask,

    // Energy
    energy,
    setEnergy,

    // User
    user: mockUser,

    // Task information
    dueTodayCount,
    atRiskCount,
    suggestedTask,

    // History
    history,
  }

  return (
    <AppContext.Provider value={value}>
      {children}
    </AppContext.Provider>
  )
}

// -----------------------------
// Hook
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

