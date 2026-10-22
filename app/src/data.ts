import type { Task } from './types'

export const chatSuggestions = [
  'What should I work on now?',
  "What's at risk today?",
  'What should my top priority be?',
  'Show my upcoming deadlines',
]

export type ChatMessage = {
  id: string
  role: 'user' | 'ai'
  text: string
  taskRef?: Task
}
