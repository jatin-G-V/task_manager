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
      const range = !end
        ? timeText(start)
        : sameDay(start, end)
          ? `${timeText(start)} – ${timeText(end)}`
          : `${timeText(start)} – ${relativeDay(end)} · ${timeText(end)}`
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

const recurrenceDays: Record<string, string> = {
  MO: 'Mon', TU: 'Tue', WE: 'Wed', TH: 'Thu',
  FR: 'Fri', SA: 'Sat', SU: 'Sun',
}

const legacyDayCodes: Record<string, string> = {
  monday: 'MO', mon: 'MO', tuesday: 'TU', tue: 'TU', tues: 'TU',
  wednesday: 'WE', wed: 'WE', thursday: 'TH', thu: 'TH', thur: 'TH', thurs: 'TH',
  friday: 'FR', fri: 'FR', saturday: 'SA', sat: 'SA', sunday: 'SU', sun: 'SU',
}

function legacyRecurrenceRule(value: string) {
  const normalized = value.trim().toLowerCase().replace(/\s+/g, ' ')
  if (['daily', 'every day'].includes(normalized)) return 'FREQ=DAILY'
  if (['every other day', 'every 2 days', 'every 2 day'].includes(normalized)) return 'FREQ=DAILY;INTERVAL=2'
  if (['monthly', 'every month'].includes(normalized)) return 'FREQ=MONTHLY'
  if (['yearly', 'annually', 'every year'].includes(normalized)) return 'FREQ=YEARLY'
  if (['weekdays', 'weekday'].includes(normalized)) return 'FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR'
  if (['weekends', 'weekend'].includes(normalized)) return 'FREQ=WEEKLY;BYDAY=SA,SU'

  const interval = normalized.match(/^(?:every )?(\d+) (day|week|month|year)s?$/)
  if (interval && Number(interval[1]) > 0) {
    const frequency: Record<string, string> = {
      day: 'DAILY', week: 'WEEKLY', month: 'MONTHLY', year: 'YEARLY',
    }
    return `FREQ=${frequency[interval[2]]};INTERVAL=${interval[1]}`
  }

  const dailyExcept = normalized.match(/^(?:daily|every day) except (.+)$/)
  const weekly = normalized.match(/^(?:weekly on|every) (.+)$/)
  const dayText = dailyExcept?.[1] ?? weekly?.[1]
  if (dayText) {
    const dayNames = dayText.split(/,|\band\b/).map((day) => day.trim())
    const days = dayNames.map((day) => legacyDayCodes[day.replace(/s$/, '')] ?? legacyDayCodes[day])
    if (days.some((day) => !day)) return null
    if (dailyExcept) {
      const excluded = new Set(days)
      const included = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU'].filter((day) => !excluded.has(day))
      return included.length ? `FREQ=WEEKLY;BYDAY=${included.join(',')}` : null
    }
    return `FREQ=WEEKLY;BYDAY=${[...new Set(days)].join(',')}`
  }

  return null
}

export function recurrenceRuleParts(value?: string | null) {
  if (!value?.trim()) return null
  let normalized = value.trim().replace(/^RRULE:/i, '').trim().toUpperCase()
  if (!normalized.startsWith('FREQ=')) {
    const converted = legacyRecurrenceRule(value)
    if (!converted) return null
    normalized = converted
  }

  const fields = Object.fromEntries(
    normalized.split(';').map((part) => {
      const [key, ...rest] = part.split('=')
      return [key, rest.join('=')]
    }),
  ) as Record<string, string>

  return {
    fields,
    frequency: fields.FREQ,
    interval: Number(fields.INTERVAL ?? '1'),
    days: fields.BYDAY?.split(',').map((day) => day.slice(-2)) ?? [],
  }
}

function ordinal(day: number) {
  const remainder = day % 100
  const suffix = remainder >= 11 && remainder <= 13
    ? 'th'
    : day % 10 === 1
      ? 'st'
      : day % 10 === 2
        ? 'nd'
        : day % 10 === 3
          ? 'rd'
          : 'th'
  return `${day}${suffix}`
}

export function recurrenceLabel(task: Task) {
  if (!task.isRecurring || !task.recurrence) return null
  const parsed = recurrenceRuleParts(task.recurrence)
  if (!parsed) return `↻ ${task.recurrence.trim()}`
  const { fields, frequency, interval } = parsed
  let label: string

  if (frequency === 'DAILY') {
    label = interval === 1 ? 'Daily' : `Every ${interval} days`
  } else if (frequency === 'WEEKLY' && fields.BYDAY) {
    const days = parsed.days
      .map((code) => recurrenceDays[code])
      .filter(Boolean)
    label = interval > 1
      ? `Every ${interval} weeks${days.length ? ` · ${days.join(' · ')}` : ''}`
      : days.join(' · ')
  } else if (frequency === 'WEEKLY') {
    label = interval === 1 ? 'Weekly' : `Every ${interval} weeks`
  } else if (frequency === 'MONTHLY') {
    const monthDay = fields.BYMONTHDAY?.split(',')[0]
    const fallbackDate = parseInstant(task.scheduledStart ?? task.deadline)
    const day = monthDay ? Number(monthDay) : fallbackDate?.getDate()
    label = `Monthly${day && day > 0 ? ` · ${ordinal(day)}` : ''}`
    if (interval > 1) label = `Every ${interval} months${day && day > 0 ? ` · ${ordinal(day)}` : ''}`
  } else if (frequency === 'YEARLY') {
    label = interval === 1 ? 'Yearly' : `Every ${interval} years`
  } else {
    label = task.recurrence.trim()
  }

  const end = parseInstant(task.recurrenceEnd)
  const until = end
    ? ` · until ${new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(end)}`
    : ''
  return `↻ ${label}${until}`
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
