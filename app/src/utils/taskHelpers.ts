import type { Task } from "../types"

export function formatDeadline(
  iso?: string,
): string {
  if (!iso) return "No deadline set"

  const date = new Date(iso)

  if (Number.isNaN(date.getTime())) {
    return "No deadline set"
  }

  const hasTime =
    date.getHours() !== 0 ||
    date.getMinutes() !== 0

  const dateStr =
    date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    })

  if (!hasTime) {
    return dateStr
  }

  const timeStr =
    date.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    })

  return `${dateStr} · ${timeStr}`
}

export function isTaskOverdue(
  task: Task,
): boolean {
  if (!task.deadline) return false

  const deadline = new Date(
    task.deadline,
  ).getTime()

  if (Number.isNaN(deadline)) {
    return false
  }

  return deadline < Date.now()
}

export function getReasonLabel(
  task: Task,
): string {
  if (
    task.scheduleType === "scheduled" ||
    task.scheduledStart
  ) {
    return "Starting now"
  }

  if (task.atRisk) {
    return "Due soon"
  }

  if (task.deadline) {
    const deadline = new Date(
      task.deadline,
    ).getTime()

    if (!Number.isNaN(deadline)) {
      const hours =
        (deadline - Date.now()) /
        (1000 * 60 * 60)

      if (hours <= 3) {
        return "Due soon"
      }
    }
  }

  return "Best next pick"
}