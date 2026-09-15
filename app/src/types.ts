export type Screen =
  | 'login'
  | 'signup'
  | 'dashboard'
  | 'drawer'
  | 'digest'
  | 'work'
  | 'personal'
  | 'leisure'
  | 'task-detail'
  | 'add-task'
  | 'history'
  | 'notifications'

export type TabSection =
  | 'home'
  | 'work'
  | 'personal'
  | 'leisure'

export type EnergyLevel =
  | 'low'
  | 'focused'
  | 'high'
  | null

export interface Task {
  id: string
  title: string
  section: 'work' | 'personal' | 'leisure'
  steps?: string[]
  brief?: string
  deadline: string
  priority: 'high' | 'medium' | 'low'
  priorityScore?: number
  priorityWhy?: string
  estimatedTime?: string
  scheduledTime?: string
  atRisk?: boolean
  blocked?: boolean
  dueToday?: boolean
  
}

export interface HistoryTask {
  id: string
  title: string
  section: 'work' | 'personal' | 'leisure'
  type: 'completed' | 'expired'
  date: string
}

export interface User {
  name: string
  email: string
  profession: string
}

export interface NavState {
  screen: Screen
  activeTab: TabSection
  selectedTask?: Task
  previousScreen?: Screen
}

export interface NavOpts {
  task?: Task
  tab?: TabSection
}

export interface Theme {
  bg: string
  surface: string
  surface2: string
  text: string
  muted: string
  border: string
  primary: string
  due: string
  risk: string
  success: string
  dueBg: string
  riskBg: string
  successBg: string
}

export interface TaskStore {
  work: Task[]
  personal: Task[]
  leisure: Task[]
}

export interface AppContextType {
  darkMode: boolean
  toggleDark: () => void
  t: Theme

  tasks: TaskStore
  completeTask: (id: string) => void
  addTask: (task: Task) => void

  energy: EnergyLevel
  setEnergy: (e: 'low' | 'focused' | 'high') => void

  user: User

  dueTodayCount: number
  atRiskCount: number
  suggestedTask: Task | null

  history: HistoryTask[]
}

