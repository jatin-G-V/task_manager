import type { Effort, Task, Theme, Urgency } from '../types'

export function parseInstant(value?: string | null) {
  if (!value) return null
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

const sameDay = (a: Date, b: Date) =>
  a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()

function relativeDay(date: Date) {
  const today = new Date()
  const tomorrow = new Date(today)
  tomorrow.setDate(today.getDate() + 1)
  if (sameDay(date, today)) return 'Today'
  if (sameDay(date, tomorrow)) return 'Tomorrow'
  return new Intl.DateTimeFormat('en-US', { weekday: 'short', month: 'short', day: 'numeric' }).format(date)
}

const timeText = (date: Date) => new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit' }).format(date)
const dateText = (date: Date) => new Intl.DateTimeFormat('en-US', { weekday: 'long', month: 'short', day: 'numeric' }).format(date)

export function timingLabel(task: Task): { text: string; tone: 'normal' | 'overdue' } {
  const start = parseInstant(task.scheduledStart)
  const end = parseInstant(task.scheduledEnd)
  const deadline = parseInstant(task.deadline)
  const relevantDate = start ?? end ?? deadline
  if ((task.isOverdue || task.atRisk && relevantDate && relevantDate < new Date()) && relevantDate) {
    return { text: `Overdue · ${new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(relevantDate)}`, tone: 'overdue' }
  }
  if (task.scheduleType === 'scheduled') {
    if (task.hasExplicitTime && start) {
      const range = end && sameDay(start, end) ? `${timeText(start)} – ${timeText(end)}` : timeText(start)
      return { text: `${relativeDay(start)} · ${range}`, tone: 'normal' }
    }
    if (start && end && sameDay(start, end)) return { text: `Anytime ${relativeDay(start).toLowerCase()}`, tone: 'normal' }
    if (start) return { text: `${relativeDay(start)} · after ${timeText(start)}`, tone: 'normal' }
    if (end) return { text: `By ${relativeDay(end)}`, tone: 'normal' }
    return { text: 'No date', tone: 'normal' }
  }
  if (deadline) return { text: `Do before · ${dateText(deadline)}${task.hasExplicitTime ? ` · ${timeText(deadline)}` : ''}`, tone: 'normal' }
  return { text: 'No deadline', tone: 'normal' }
}

export const whenLabel = (task: Task) => timingLabel(task).text

export function recurrenceLabel(task: Task) {
  if (!task.isRecurring || !task.recurrence) return null
  const value = task.recurrence.trim().toLowerCase()
  if (['daily', 'monthly', 'yearly'].includes(value)) return `↻ ${value[0].toUpperCase()}${value.slice(1)}`
  if (value.startsWith('weekly on ')) {
    const days = value.replace('weekly on ', '').replace(' and ', ', ').split(',').map((day) => day.trim()).filter(Boolean)
    return days.length === 1 ? `↻ Every ${days[0][0].toUpperCase()}${days[0].slice(1)}` : `↻ ${days.map((day) => day.slice(0, 3)).map((day) => day[0].toUpperCase() + day.slice(1)).join(' · ')}`
  }
  return `↻ ${value[0].toUpperCase()}${value.slice(1)}`
}

export function urgencyLabel(value: Urgency | undefined, t: Theme) {
  if (!value) return null
  const palette = { low: ['#3DAF72', '#3DAF7220'], medium: ['#B08A00', '#F5C84220'], high: ['#E9713C', '#E9713C20'], urgent: [t.risk, t.riskBg] }
  return { text: value[0].toUpperCase() + value.slice(1), color: palette[value][0], bg: palette[value][1] }
}

export function effortLabel(value: Effort | undefined) {
  if (!value) return null
  const palette = { low: ['#3DAF72', '#3DAF7220'], medium: ['#B08A00', '#F5C84220'], high: ['#E9713C', '#E9713C20'] }
  return { text: `${value[0].toUpperCase()}${value.slice(1)} effort`, color: palette[value][0], bg: palette[value][1] }
}
