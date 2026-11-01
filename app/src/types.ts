
export type EnergyLevel =
  | 'low'
  | 'focused'
  | 'high'
  | null

export type Effort = 'low' | 'medium' | 'high' | null
export type Urgency = 'low' | 'medium' | 'high' | 'urgent' | null
export type ScheduleType = 'scheduled' | 'flexible'
export type TaskSection = 'work' | 'personal' | 'leisure'

export interface Task {
  id: string
  title: string
  section: 'work' | 'personal' | 'leisure'
  steps?: string[]
  brief?: string
  deadline: string | null
  priority: 'high' | 'medium' | 'low'
  priorityScore?: number
  priorityWhy?: string
  estimatedTime?: string
  scheduledTime?: string
  atRisk?: boolean
  reason?: 'pinned' | 'deadline_risk' | 'energy_match' | 'top_score' | 'upcoming'
  dueToday?: boolean
  effort?: Effort
  urgency?: Urgency
  scheduleType?: ScheduleType
  scheduledStart?: string | null
  scheduledEnd?: string | null
  hasExplicitTime?: boolean
  blocked?: boolean
  isBlocked?: boolean
  isOverdue?: boolean
  isRecurring?: boolean
  recurrence?: string | null
  recurrenceEnd?: string | null
  completed?: boolean
}

export type TaskUpdates = Partial<Pick<Task,
  'title' | 'brief' | 'effort' | 'urgency' | 'deadline' |
  'scheduleType' | 'scheduledStart' | 'scheduledEnd' | 'hasExplicitTime' |
  'isBlocked' | 'isRecurring' | 'recurrence' | 'recurrenceEnd'
>>

export interface HistoryTask {
  id: string
  title: string
  section: 'work' | 'personal' | 'leisure' | null
  type: 'completed' | 'expired'
  date: string
}

export interface User {
  name: string
  email: string
  profession: string
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
  completeTask: (id: string) => Promise<void>
  deleteTask: (id: string, section: TaskSection) => Promise<void>
  addTask: (task: Task) => Promise<void>
  updateTask: (id: string, section: TaskSection, updates: TaskUpdates) => Promise<void>
  energy: EnergyLevel
  setEnergy: (e: EnergyLevel) => void

  user: User
  overdueCount: number
  suggestedList: Task[]
  rankedTasks: Task[]
  overdueTasks: Task[]
  dueTodayTasks: Task[]
  scheduledTodayTasks: Task[]
  atRiskTasks: Task[]
  dueTodayCount: number
  atRiskCount: number
  suggestedTask: Task | null
  history: HistoryTask[]
  refreshTasks: () => Promise<void>
}
