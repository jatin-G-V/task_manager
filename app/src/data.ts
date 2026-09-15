import type { Task, HistoryTask, User } from './types'

export const mockUser: User = {
  name: 'Jatin Garg',
  email: 'gargjatin531@gmail.com',
  profession: 'Software Engineer',
}

export const initialTasks = {
  work: [
    {
      id: 'w1',
      title: 'Q3 Product Roadmap Review',
      brief:
        'Compile insights from Q2 retrospective and align stakeholders on H2 priorities before the leadership sync.',
      deadline: 'Today, 3:00 PM',
      section: 'work' as const,
      priority: 'high' as const,
      priorityScore: 94,
      priorityWhy:
        'Deadline is today and three stakeholders are blocked waiting on your input.',
      estimatedTime: '2 hours',
      atRisk: true,
      dueToday: true,
      steps: [
        'Review Q2 metrics and KPIs',
        'Draft H2 priority list',
        'Align with design team lead',
        'Prepare slide deck (5 slides max)',
        'Send preview to Lisa before 1 PM',
      ],
    },
    {
      id: 'w2',
      title: 'Design System Audit',
      brief:
        'Document inconsistencies across component library and propose a consolidation plan.',
      deadline: 'Tomorrow, 11:00 AM',
      section: 'work' as const,
      priority: 'medium' as const,
      priorityScore: 71,
      priorityWhy:
        'Scheduled for tomorrow but prep work needs to start today.',
      estimatedTime: '3 hours',
      dueToday: false,
      steps: [
        'Export component inventory from Figma',
        'Flag duplicates and naming conflicts',
        'Write consolidation proposal doc',
        'Share with engineering for feasibility check',
      ],
    },
    {
      id: 'w3',
      title: 'User Interview Prep',
      brief:
        'Prepare discussion guide and screener questions for the mobile usability study.',
      deadline: 'Wed, Sep 13',
      section: 'work',
      priority: 'medium',
      priorityScore: 58,
      priorityWhy:
        'Research ops needs your guide by EOD Tuesday.',
      estimatedTime: '1.5 hours',
      blocked: true,
      steps: [
        'Review previous interview notes',
        'Draft 8 open-ended questions',
        'Add screener criteria',
        'Send to research ops for scheduling',
      ],
    },
    {
      id: 'w4',
      title: 'Figma Component Library Update',
      brief:
        'Update button, input, and card components to match new brand tokens.',
      deadline: 'Fri, Sep 15',
      section: 'work',
      priority: 'low',
      priorityScore: 42,
      priorityWhy:
        'End-of-week deadline with no blocking dependencies.',
      estimatedTime: '4 hours',
    },
  ] as Task[],

  personal: [
    {
      id: 'p1',
      title: 'Call dentist for checkup',
      deadline: 'Today',
      section: 'personal',
      priority: 'high',
      dueToday: true,
    },
    {
      id: 'p2',
      title: 'Grocery shopping',
      deadline: 'Today, 6:00 PM',
      section: 'personal',
      priority: 'medium',
      dueToday: true,
    },
    {
      id: 'p3',
      title: 'Book flights for October trip',
      deadline: 'Sep 20',
      section: 'personal',
      priority: 'low',
    },
  ] as Task[],

  leisure: [
    {
      id: 'l1',
      title: "Finish reading 'Deep Work'",
      deadline: 'This week',
      section: 'leisure',
      priority: 'low',
    },
    {
      id: 'l2',
      title: 'Evening yoga session',
      deadline: 'Today, 7:00 PM',
      section: 'leisure',
      priority: 'medium',
      scheduledTime: '7:00 PM',
      dueToday: true,
    },
  ] as Task[],
}

export const initialHistory: HistoryTask[] = [
  {
    id: 'h1',
    title: 'Weekly team sync notes',
    section: 'work',
    type: 'completed',
    date: 'Sep 10, 2026',
  },
  {
    id: 'h2',
    title: 'Competitive analysis slides',
    section: 'work',
    type: 'completed',
    date: 'Sep 10, 2026',
  },
  {
    id: 'h3',
    title: 'Morning run — 5k',
    section: 'leisure',
    type: 'completed',
    date: 'Sep 9, 2026',
  },
  {
    id: 'h4',
    title: 'Pay electricity bill',
    section: 'personal',
    type: 'expired',
    date: 'Sep 8, 2026',
  },
  {
    id: 'h5',
    title: 'Review onboarding flow v2',
    section: 'work',
    type: 'completed',
    date: 'Sep 8, 2026',
  },
  {
    id: 'h6',
    title: 'Call insurance for renewal',
    section: 'personal',
    type: 'expired',
    date: 'Sep 7, 2026',
  },
  {
    id: 'h7',
    title: 'Cook dinner with friends',
    section: 'leisure',
    type: 'completed',
    date: 'Sep 6, 2026',
  },
  {
    id: 'h8',
    title: 'Sprint planning prep',
    section: 'work',
    type: 'completed',
    date: 'Sep 5, 2026',
  },
]

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

export function getAIResponse(
  query: string,
  tasks: typeof initialTasks,
): { text: string; taskRef?: Task } {
  const q = query.toLowerCase()

  if (
    q.includes('work on') ||
    q.includes('focus') ||
    q.includes('now')
  ) {
    return {
      text: "Based on your energy level and today's deadlines, I'd recommend tackling your roadmap review first — it's due at 3 PM and you'll need a clear head for it.",
      taskRef: tasks.work[0],
    }
  }

  if (q.includes('risk') || q.includes('urgent')) {
    return {
      text: "Your Q3 Roadmap Review is at risk — it's due today at 3 PM and hasn't been started. That's your most pressing item right now.",
      taskRef: tasks.work[0],
    }
  }

  if (q.includes('priority') || q.includes('top')) {
    return {
      text: 'Your highest-priority task right now is the Q3 Roadmap Review (score 94/100). Three stakeholders are waiting, and the window to finish before the 3 PM meeting is narrowing.',
      taskRef: tasks.work[0],
    }
  }

  if (q.includes('deadline') || q.includes('upcoming')) {
    return {
      text: 'You have 3 tasks due today: Q3 Roadmap Review (3 PM), Call dentist, and Grocery shopping (6 PM). Tomorrow: Design System Audit at 11 AM.',
    }
  }

  return {
    text: "I'll look into that. Based on your current tasks and energy, I'd suggest finishing your roadmap review before diving into anything else — it's the highest stakes item on your plate today.",
    taskRef: tasks.work[0],
  }
}

