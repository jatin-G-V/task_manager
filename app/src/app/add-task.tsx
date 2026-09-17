import React, { useState } from 'react'
import {
  View,
  Text,
  ScrollView,
  Pressable,
  TextInput,
  StyleSheet,
} from 'react-native'
import { useRouter } from 'expo-router'

import { useApp } from '../context/AppContext'
import {
  ChevronLeft,
  Mic,
  Sparkles,
  Check,
} from '../components/icons'
import type { Task } from '../types'
import { SafeAreaView } from 'react-native-safe-area-context'
function classifySection(
  title: string
): 'work' | 'personal' | 'leisure' {
  const text = title.toLowerCase()

  const workWords = [
    'meeting',
    'report',
    'project',
    'client',
    'deadline',
    'review',
    'design',
    'email',
    'call',
    'presentation',
    'sprint',
    'deploy',
    'code',
    'build',
  ]

  const leisureWords = [
    'read',
    'watch',
    'game',
    'gym',
    'run',
    'yoga',
    'music',
    'movie',
    'book',
    'walk',
    'hike',
    'cook',
    'garden',
  ]

  if (workWords.some(word => text.includes(word))) {
    return 'work'
  }

  if (leisureWords.some(word => text.includes(word))) {
    return 'leisure'
  }

  return 'personal'
}

export default function AddTaskScreen() {
  const router = useRouter()
  const { t, addTask } = useApp()

  const [input, setInput] = useState('')
  const [recording, setRecording] = useState(false)
  const [saved, setSaved] = useState(false)

  const [assignedSection, setAssignedSection] =
    useState<'work' | 'personal' | 'leisure' | null>(null)

  const handleSave = async () => {
  if (!input.trim() || !assignedSection) return

  try {
    const task: Task = {
      id: '',
      title: input.trim(),
      deadline: 'No deadline set',
      section: assignedSection,
      priority: 'medium',
    }

    await addTask(task)

    setSaved(true)

    setTimeout(() => {
      router.back()
    }, 1200)
  } catch (error) {
    console.error('Failed to save task:', error)
  }
}

  const toggleRecording = () => {
    setRecording(value => !value)

    if (recording) {
      setInput(prev =>
        prev
          ? prev
          : 'Voice note: follow up with the team about sprint planning'
      )
    }
  }

  const sectionLabel = {
    work: '💼 Work',
    personal: '🌿 Personal',
    leisure: '☕ Leisure',
  }

  // -------------------------
  // Saved screen
  // -------------------------

  if (saved && assignedSection) {
    return (
      <SafeAreaView
        style={[
          styles.savedContainer,
          { backgroundColor: t.bg },
        ]}
      >
        <View
          style={[
            styles.successCircle,
            { backgroundColor: t.success },
          ]}
        >
          <Check size={28} color="#FFFFFF" />
        </View>

        <View style={styles.savedTextContainer}>
          <Text
            style={[
              styles.savedTitle,
              { color: t.text },
            ]}
          >
            Task saved
          </Text>

          <Text
            style={[
              styles.savedSubtitle,
              { color: t.muted },
            ]}
          >
            AI assigned to{' '}
            <Text
              style={[
                styles.assignedText,
                { color: t.text },
              ]}
            >
              {sectionLabel[assignedSection]}
            </Text>
          </Text>
        </View>
      </SafeAreaView>
    )
  }

  // -------------------------
  // New Task screen
  // -------------------------

  return (
    <SafeAreaView
      style={[
        styles.container,
        { backgroundColor: t.bg },
      ]}
    >
      {/* Header */}
      <View style={styles.header}>
        <Pressable
          onPress={() => router.back()}
          style={styles.backButton}
        >
          <ChevronLeft
            size={18}
            color={t.muted}
          />

          <Text
            style={[
              styles.backText,
              { color: t.muted },
            ]}
          >
            Back
          </Text>
        </Pressable>

        <Text
          style={[
            styles.title,
            { color: t.text },
          ]}
        >
          New Task
        </Text>

        <View style={styles.aiInfo}>
          <Sparkles
            size={13}
            color={t.primary}
          />

          <Text
            style={[
              styles.aiText,
              { color: t.muted },
            ]}
          >
            Choose a section for now — AI will take over later
          </Text>
        </View>
      </View>

      <ScrollView
        style={styles.body}
        contentContainerStyle={styles.bodyContent}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        {/* Text input */}
<View>
  <Text
    style={[
      styles.label,
      { color: t.muted },
    ]}
  >
    What needs to get done?
  </Text>

  <TextInput
    value={input}
    onChangeText={setInput}
    placeholder="e.g. Review the onboarding flow and send feedback to the team"
    placeholderTextColor={t.muted}
    multiline
    numberOfLines={4}
    textAlignVertical="top"
    style={[
      styles.textInput,
      {
        backgroundColor: t.surface,
        borderColor: t.border,
        color: t.text,
      },
    ]}
  />
</View>

{/* SECTION */}
<View style={styles.sectionContainer}>
  <Text
    style={[
      styles.label,
      { color: t.muted },
    ]}
  >
    Where does this task belong?
  </Text>

  <View style={styles.sectionRow}>
    {[
      {
        id: 'work',
        label: '💼 Work',
      },
      {
        id: 'personal',
        label: '🌿 Personal',
      },
      {
        id: 'leisure',
        label: '☕ Leisure',
      },
    ].map((section) => {
      const selected = assignedSection === section.id

      return (
        <Pressable
          key={section.id}
          onPress={() =>
            setAssignedSection(
              section.id as 'work' | 'personal' | 'leisure'
            )
          }
          style={[
            styles.sectionButton,
            {
              backgroundColor: selected
                ? t.primary
                : t.surface,
              borderColor: selected
                ? t.primary
                : t.border,
            },
          ]}
        >
          <Text
            style={{
              color: selected
                ? '#FFFFFF'
                : t.text,
              fontSize: 13,
              fontWeight: '600',
            }}
          >
            {section.label}
          </Text>
        </Pressable>
      )
    })}
  </View>
</View>


        {/* Divider */}
        <View style={styles.dividerRow}>
          <View
            style={[
              styles.divider,
              { backgroundColor: t.border },
            ]}
          />

          <Text
            style={[
              styles.orText,
              { color: t.muted },
            ]}
          >
            or
          </Text>

          <View
            style={[
              styles.divider,
              { backgroundColor: t.border },
            ]}
          />
        </View>

        {/* Voice input */}
        <Pressable
          onPress={toggleRecording}
          style={[
            styles.voiceCard,
            {
              backgroundColor: recording
                ? `${t.risk}12`
                : t.surface,

              borderColor: recording
                ? t.risk
                : t.border,
            },
          ]}
        >
          <View
            style={[
              styles.micCircle,
              {
                backgroundColor: recording
                  ? t.risk
                  : t.surface2,
              },
            ]}
          >
            <Mic
              size={24}
              color={
                recording
                  ? '#FFFFFF'
                  : t.muted
              }
            />
          </View>

          <View style={styles.voiceText}>
            <Text
              style={[
                styles.voiceTitle,
                {
                  color: recording
                    ? t.risk
                    : t.text,
                },
              ]}
            >
              {recording
                ? 'Recording… tap to stop'
                : 'Record with voice'}
            </Text>

            <Text
              style={[
                styles.voiceSubtitle,
                { color: t.muted },
              ]}
            >
              {recording
                ? 'Listening to your task…'
                : 'Tap the mic to speak'}
            </Text>
          </View>
        </Pressable>

        {/* Spacer */}
        <View style={styles.spacer} />

        {/* Save */}
        <Pressable
          onPress={handleSave}
          disabled={!input.trim() || !assignedSection}
          style={[
            styles.saveButton,
            {
              backgroundColor: input.trim()
                ? t.primary
                : t.border,
            },
          ]}
        >
          <Text
            style={[
              styles.saveText,
              {
                color: input.trim()
                  ? '#FFFFFF'
                  : t.muted,
              },
            ]}
          >
            Save Task
          </Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },

  header: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 16,
  },

  backButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 16,
  },

  backText: {
    fontSize: 14,
    fontFamily: 'Outfit',
  },

  title: {
    fontSize: 22,
    fontWeight: '700',
    fontFamily: 'DM Serif Display',
  },

  aiInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 6,
  },

  aiText: {
    fontSize: 12.5,
    fontFamily: 'Outfit',
  },

  body: {
    flex: 1,
  },

  bodyContent: {
    paddingHorizontal: 20,
    paddingBottom: 24,
    flexGrow: 1,
  },

  label: {
    fontSize: 12.5,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.7,
    marginBottom: 10,
    fontFamily: 'Outfit',
  },

  textInput: {
    width: '100%',
    minHeight: 120,
    borderRadius: 16,
    borderWidth: 1.5,
    paddingHorizontal: 16,
    paddingVertical: 16,
    fontSize: 15,
    lineHeight: 24,
    fontFamily: 'Outfit',
  },

  dividerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginVertical: 20,
  },

  divider: {
    flex: 1,
    height: 1,
  },

  orText: {
    fontSize: 12,
    fontWeight: '500',
    fontFamily: 'Outfit',
  },

  voiceCard: {
    width: '100%',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
    borderRadius: 16,
    paddingVertical: 32,
    borderWidth: 1.5,
  },

  micCircle: {
    width: 56,
    height: 56,
    borderRadius: 999,
    alignItems: 'center',
    justifyContent: 'center',
  },

  voiceText: {
    alignItems: 'center',
  },

  voiceTitle: {
    fontSize: 15,
    fontWeight: '600',
    fontFamily: 'Outfit',
  },

  voiceSubtitle: {
    fontSize: 12.5,
    marginTop: 2,
    fontFamily: 'Outfit',
  },

  spacer: {
    flex: 1,
    minHeight: 24,
  },

  saveButton: {
    width: '100%',
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },

  saveText: {
    fontSize: 16,
    fontWeight: '600',
    fontFamily: 'Outfit',
  },

  savedContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 32,
    gap: 16,
  },

  successCircle: {
    width: 64,
    height: 64,
    borderRadius: 999,
    alignItems: 'center',
    justifyContent: 'center',
  },

  savedTextContainer: {
    alignItems: 'center',
  },

  savedTitle: {
    fontSize: 18,
    fontWeight: '700',
    marginBottom: 6,
    fontFamily: 'DM Serif Display',
  },

  savedSubtitle: {
    fontSize: 14,
    fontFamily: 'Outfit',
  },

  assignedText: {
    fontWeight: '600',
    fontFamily: 'Outfit',
  },
  sectionContainer: {
  marginTop: 20,
},

sectionRow: {
  flexDirection: 'row',
  gap: 8,
},

sectionButton: {
  flex: 1,
  paddingVertical: 12,
  borderRadius: 12,
  borderWidth: 1.5,
  alignItems: 'center',
  justifyContent: 'center',
},
})