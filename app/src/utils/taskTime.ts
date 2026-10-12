import type { Task } from '../types'

// ------------------------------------------------------------
// The backend now returns real instants (UTC, for example
// "2026-10-04T10:30:00+00:00"). Parse them as real instants so
// the phone shows them in its own local time zone.
//
// Keep the phone's time zone equal to APP_TIMEZONE on the backend
// (default Asia/Kolkata). Later this can become a per-user setting.
// ------------------------------------------------------------
export function parseInstant(iso?: string | null): Date | null {
  if (!iso) return null

  // Be tolerant of Postgres style strings: "2026-10-04 10:30:00+00"
  let s = iso.trim().replace(' ', 'T')

  // "+00" / "-05" -> "+00:00" / "-05:00"
  s = s.replace(/([+-]\d{2})$/, '$1:00')

  // No offset at all -> treat as local wall-clock time
  const d = new Date(s)

  return isNaN(d.getTime()) ? null : d
}

// Old name, kept so existing imports keep working.
export const parseWall = parseInstant

const sameDay = (a: Date, b: Date) =>
  a.getFullYear() === b.getFullYear() &&
  a.getMonth() === b.getMonth() &&
  a.getDate() === b.getDate()

const dayWord = (d: Date): string => {
  const today = new Date()
  today.setHours(0, 0, 0, 0)

  const day = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const diff = Math.round((day.getTime() - today.getTime()) / 86400000)

  if (diff === 0) return 'today'
  if (diff === 1) return 'tomorrow'
  if (diff === -1) return 'yesterday'

  return d.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  })
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

const clock = (d: Date) =>
  d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })

// ------------------------------------------------------------
// One readable "when" line for any kind of task
//   scheduled + exact time   -> "Today · 3:00 PM"
//   scheduled, vague window  -> "Anytime tomorrow" / "Today · after 6:00 PM" / "By Fri, Oct 3"
//   flexible with deadline   -> "Due today · 5:00 PM" / "Due Fri, Oct 3"
//   nothing                  -> "No deadline"
// ------------------------------------------------------------
export function whenLabel(task: Task): string {
  const start = parseInstant(task.scheduledStart)
  const end = parseInstant(task.scheduledEnd)
  const deadline = parseInstant(task.deadline)

  if (task.scheduleType === 'scheduled' && start) {
    if (task.hasExplicitTime) {
      return `${cap(dayWord(start))} · ${clock(start)}`
    }

    if (end && !sameDay(start, end)) {
      return `By ${dayWord(end)}`
    }

    if (end && start.getHours() === 0 && end.getHours() === 23) {
      return `Anytime ${dayWord(end)}`
    }

    if (end && end.getHours() === 23 && end.getMinutes() === 59) {
      return `${cap(dayWord(start))} · after ${clock(start)}`
    }

    if (end) {
      return `${cap(dayWord(start))} · ${clock(start)}–${clock(end)}`
    }

    return cap(dayWord(start))
  }

  if (deadline) {
    return task.hasExplicitTime
      ? `Due ${dayWord(deadline)} · ${clock(deadline)}`
      : `Due ${dayWord(deadline)}`
  }

  return 'No deadline'
}

// The backend can also send reason = "upcoming" (tasks that have not
// started yet). It is matched as a plain string so the Task type does
// not have to change.
export function reasonLabel(reason?: Task['reason']): string {
  switch (reason as string | undefined) {
    case 'pinned':
      return 'Starting now'
    case 'deadline_risk':
      return 'Due soon'
    case 'energy_match':
      return 'Fits your energy'
    case 'top_score':
      return 'Best next pick'
    case 'upcoming':
      return 'Coming up'
    default:
      return 'Up next'
  }
}

export function greeting(name?: string): string {
  const hour = new Date().getHours()

  const part =
    hour < 12
      ? 'Good morning'
      : hour < 17
      ? 'Good afternoon'
      : 'Good evening'

  const first = name ? name.split(' ')[0] : ''

  return first ? `${part}, ${first}` : part
}