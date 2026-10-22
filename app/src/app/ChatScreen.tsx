import { useEffect, useRef, useState } from "react"
import { useRouter, useLocalSearchParams } from "expo-router"
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native"
import {
  RecordingPresets,
  requestRecordingPermissionsAsync,
  setAudioModeAsync,
  useAudioRecorder,
} from "expo-audio"
import { File } from "expo-file-system"
import { chatSuggestions } from "../data"
import { useSafeAreaInsets } from "react-native-safe-area-context"
import { useApp } from "../context/AppContext"
import type { ChatMessage } from "../data"
import { ChevronLeft, ChevronRight, Mic, Send, Sparkles } from "../components/icons"
import { apiFetch } from "../lib/apiClient"
import { supabase } from "../lib/supabase"

const MAX_RECORDING_MS = 60_000

function formatRecordingTime(seconds: number) {
  const minutes = Math.floor(seconds / 60)
  const remainder = seconds % 60
  return `${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`
}

let chatCache: {
  email: string
  messages: ChatMessage[]
} | null = null

export default function ChatScreen() {
  const {
  t,
  user,
  refreshTasks,
} = useApp()

const router = useRouter()

const { prefill } = useLocalSearchParams<{
  prefill?: string
}>()

  const insets = useSafeAreaInsets()

  const [chatInput, setChatInput] = useState(prefill ?? "")

const firstName = user.name ? user.name.split(" ")[0] : ""

const initial: ChatMessage = {
  id: "init",
  role: "ai",
  text: firstName
    ? `Hi ${firstName}. Add a task or ask me anything about your day.`
    : "Hi. Add a task or ask me anything about your day.",
}

const [messages, setMessages] = useState<ChatMessage[]>(() =>
  chatCache && chatCache.email === user.email
    ? chatCache.messages
    : [initial]
)

useEffect(() => {
  chatCache = {
    email: user.email,
    messages,
  }
}, [messages, user.email])

  const [chatActive, setChatActive] = useState(
  Boolean(prefill) || messages.length > 1
)
  const [sending, setSending] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [isTranscribing, setIsTranscribing] = useState(false)
  const [recordingSeconds, setRecordingSeconds] = useState(0)
  const scrollRef = useRef<ScrollView>(null)
  const recorder = useAudioRecorder({
    ...RecordingPresets.HIGH_QUALITY,
    isMeteringEnabled: true,
  })
  const recorderRef = useRef(recorder)
  recorderRef.current = recorder
  const autoStopTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const recordingStartedAt = useRef<number | null>(null)
  const recordingUriRef = useRef<string | null>(null)
  const stopInProgress = useRef(false)
  const meteringAvailable = useRef(false)
  const speechDetected = useRef(false)

  useEffect(() => {
    if (!isRecording) return

    const interval = setInterval(() => {
      const startedAt = recordingStartedAt.current
      if (startedAt !== null) {
        setRecordingSeconds(Math.min(60, Math.floor((Date.now() - startedAt) / 1000)))
      }
      // A pending interval tick can race with Expo releasing the native
      // recorder as this screen unmounts. Ignore status reads in that window.
      try {
        const level = recorderRef.current.getStatus().metering
        if (typeof level === "number") {
          meteringAvailable.current = true
          if (level > -50) speechDetected.current = true
        }
      } catch {
        // The recorder is being released by useAudioRecorder.
      }
    }, 250)

    return () => clearInterval(interval)
  }, [isRecording])

  useEffect(() => () => {
    if (autoStopTimer.current) clearTimeout(autoStopTimer.current)
    // useAudioRecorder owns and releases its native recorder on unmount.
    // Do not inspect or stop that shared object here: it may already be
    // released by the time this cleanup runs. The URI is a plain string, so
    // the temporary file can still be removed safely.
    if (recordingUriRef.current) {
      try {
        const tempFile = new File(recordingUriRef.current)
        if (tempFile.exists) tempFile.delete()
      } catch (error) {
        console.warn("Could not delete temporary voice recording", error)
      }
    }
    void setAudioModeAsync({ allowsRecording: false }).catch(() => undefined)
  }, [])

  const transcribeRecording = async () => {
    if (stopInProgress.current) return
    stopInProgress.current = true
    if (autoStopTimer.current) {
      clearTimeout(autoStopTimer.current)
      autoStopTimer.current = null
    }

    let recordingUri: string | null = null
    setIsRecording(false)
    setIsTranscribing(true)

    try {
      const recordingDuration = recordingStartedAt.current
        ? Date.now() - recordingStartedAt.current
        : 0
      try {
        await recorder.stop()
      } finally {
        recordingUri = recorder.uri
        recordingUriRef.current = recordingUri
      }
      if (recordingDuration < 350) {
        throw new Error("That recording was too short. Please speak in English and try again.")
      }
      if (!recordingUri) {
        throw new Error("No recording was created. Please try again.")
      }

      if (meteringAvailable.current && !speechDetected.current) {
        throw new Error("I didn't detect speech. Please speak in English and try again.")
      }

      const audioFile = new File(recordingUri)
      if (!audioFile.exists || !audioFile.size) {
        throw new Error("The recording was empty. Please try speaking and record again.")
      }

      const { data: { session } } = await supabase.auth.getSession()
      if (!session) throw new Error("Please sign in again before using voice input.")

      const recordingPath = recordingUri.toLowerCase().split("?")[0]
      const mimeType = recordingPath.endsWith(".webm")
        ? "audio/webm"
        : recordingPath.endsWith(".m4a")
          ? "audio/m4a"
          : recordingPath.endsWith(".aac")
            ? "audio/aac"
            : "audio/m4a"
      const response = await fetch(`${process.env.EXPO_PUBLIC_API_URL}/transcribe`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": mimeType,
          "X-Audio-Mime-Type": mimeType,
        },
        body: audioFile,
      })
      const result = await response.json().catch(() => ({}))
      if (!response.ok) {
        const detail = typeof result.detail === "string" ? result.detail : ""
        if (
          response.status === 422 &&
          detail.toLowerCase().includes("couldn't hear any words")
        ) {
          Alert.alert("No speech detected", "I couldn't hear any words. Please speak and try again.")
          return
        }

        console.error("Voice transcription request failed", {
          status: response.status,
          detail,
          mimeType,
          audioBytes: audioFile.size,
        })
        throw new Error(detail || "Transcription failed. Please try again.")
      }

      const transcript = typeof result.text === "string" ? result.text.trim() : ""
      if (!transcript) {
        throw new Error("I couldn't hear any words. Please try recording again.")
      }

      setChatInput((previous) => {
        const existing = previous.trimEnd()
        return existing ? `${existing} ${transcript}` : transcript
      })
    } catch (error) {
      Alert.alert(
        "Voice input",
        error instanceof Error ? error.message : "Transcription failed. Please try again."
      )
    } finally {
      if (recordingUri) {
        try {
          const tempFile = new File(recordingUri)
          if (tempFile.exists) tempFile.delete()
        } catch (error) {
          console.warn("Could not delete temporary voice recording", error)
        }
        recordingUriRef.current = null
      }
      await setAudioModeAsync({ allowsRecording: false }).catch(() => undefined)
      setIsTranscribing(false)
      setRecordingSeconds(0)
      recordingStartedAt.current = null
      stopInProgress.current = false
    }
  }

  const startRecording = async () => {
    if (sending || isTranscribing || stopInProgress.current) return

    try {
      const permission = await requestRecordingPermissionsAsync()
      if (!permission.granted) {
        Alert.alert("Microphone access", "Allow microphone access to use voice input.")
        return
      }

      await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true })
      await recorder.prepareToRecordAsync()
      recorder.record()
      recordingUriRef.current = recorder.uri ?? null
      recordingStartedAt.current = Date.now()
      meteringAvailable.current = false
      speechDetected.current = false
      setRecordingSeconds(0)
      setIsRecording(true)
      autoStopTimer.current = setTimeout(() => {
        void transcribeRecording()
      }, MAX_RECORDING_MS)
    } catch (error) {
      await setAudioModeAsync({ allowsRecording: false }).catch(() => undefined)
      Alert.alert(
        "Voice input",
        error instanceof Error ? error.message : "Could not start recording. Please try again."
      )
    }
  }

  const sendMessage = async (text: string) => {
  const trimmed = text.trim()

  if (!trimmed || sending || isRecording || isTranscribing) return

  const userMessage: ChatMessage = {
    id: `u${Date.now()}`,
    role: "user",
    text: trimmed,
  }

  setMessages((previous) => [...previous, userMessage])
  setChatInput("")
  setChatActive(true)
  setSending(true)

  try {
    const result = await apiFetch("/agent/chat", {
      method: "POST",
      body: JSON.stringify({
        messages: [
        ...messages
          .filter((message) => message.id !== "init")
          .map((message) => ({
            role: message.role === "ai" ? "assistant" : "user",
            content: message.text,
          })),
        {
          role: "user",
          content: trimmed,
        },
      ],
      }),
    })

    setMessages((previous) => [
      ...previous,
      {
        id: `a${Date.now()}`,
        role: "ai",
        text: result.reply,
      },
    ])

    if (result.tasks_changed) {
      await refreshTasks()
    }
  } catch (error) {
    console.error("Chat request failed:", error)

    setMessages((previous) => [
      ...previous,
      {
        id: `a${Date.now()}`,
        role: "ai",
        text: "Something went wrong. Please try again.",
      },
    ])
  } finally {
    setSending(false)
  }
}

  return (
    <KeyboardAvoidingView
      style={[styles.container, { backgroundColor: t.bg }]}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      keyboardVerticalOffset={Platform.OS === "ios" ? 0 : 0}
    >
      {/* Header */}
      <View
        style={[
          styles.header,
          {
            paddingTop: insets.top + 12,
            borderBottomColor: t.border,
          },
        ]}
      >
        <Pressable
          onPress={() => router.back()}
          style={({ pressed }) => [
            styles.backButton,
            {
              backgroundColor: t.surface,
              opacity: pressed ? 0.6 : 1,
            },
          ]}
          accessibilityLabel="Back"
        >
          <ChevronLeft size={18} color={t.muted} />
        </Pressable>

        <View
          style={[
            styles.aiIcon,
            {
              backgroundColor: t.primary,
            },
          ]}
        >
          <Sparkles size={17} color="#FFFFFF" />
        </View>

        <View style={styles.headerText}>
          <Text
            style={[
              styles.title,
              {
                color: t.text,
              },
            ]}
          >
            Ask AI
          </Text>

          <Text
            style={[
              styles.subtitle,
              {
                color: t.muted,
              },
            ]}
          >
            Tasks and planning
          </Text>
        </View>
      </View>

      {/* Messages */}
      <ScrollView
        ref={scrollRef}
        style={styles.messagesContainer}
        contentContainerStyle={styles.messagesContent}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
        onContentSizeChange={() =>
          scrollRef.current?.scrollToEnd({ animated: true })
        }
      >
        {messages.map((message) => {
          const isUser = message.role === "user"

          return (
            <View
              key={message.id}
              style={[
                styles.messageRow,
                isUser
                  ? styles.userMessageRow
                  : styles.aiMessageRow,
              ]}
            >
              <View style={styles.messageWrapper}>
                <View
                  style={[
                    styles.messageBubble,
                    {
                      backgroundColor: isUser
                        ? t.primary
                        : t.surface,

                      borderWidth: isUser ? 0 : 1,

                      borderColor: t.border,
                    },
                  ]}
                >
                  <Text
                    style={[
                      styles.messageText,
                      {
                        color: isUser ? "#FFFFFF" : t.text,
                      },
                    ]}
                  >
                    {message.text}
                  </Text>
                </View>

                {/* Referenced task */}
                {message.taskRef && (
                  <Pressable
                    onPress={() =>
                    router.push({
                        pathname: "/task-details",
                        params: {
                        id: message.taskRef!.id,
                        section: message.taskRef!.section,
                        },
                    })
                    }
                    style={({ pressed }) => [
                      styles.taskReference,
                      {
                        backgroundColor: t.surface,
                        borderColor: t.border,
                        opacity: pressed ? 0.7 : 1,
                      },
                    ]}
                  >
                    <View style={styles.taskReferenceContent}>
                      <Text
                        numberOfLines={1}
                        style={[
                          styles.taskReferenceTitle,
                          {
                            color: t.text,
                          },
                        ]}
                      >
                        {message.taskRef.title}
                      </Text>

                      <ChevronRight
                        size={13}
                        color={t.muted}
                      />
                    </View>
                  </Pressable>
                )}
              </View>
            </View>
          )
        })}
        {sending && (
          <View style={[styles.messageRow, styles.aiMessageRow]}>
            <View
              style={[
                styles.messageBubble,
                {
                  backgroundColor: t.surface,
                  borderWidth: 1,
                  borderColor: t.border,
                },
              ]}
            >
              <Text
                style={[
                  styles.messageText,
                  {
                    color: t.muted,
                  },
                ]}
              >
                Thinking…
              </Text>
            </View>
          </View>
        )}
      </ScrollView>

      {/* Suggestions */}
      {!chatActive && (
        <View
          style={[
            styles.suggestionsContainer,
            {
              paddingBottom: 12,
            },
          ]}
        >
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.suggestionsContent}
            keyboardShouldPersistTaps="handled"
          >
            {chatSuggestions.map((suggestion) => (
              <Pressable
                key={suggestion}
                onPress={() => sendMessage(suggestion)}
                style={({ pressed }) => [
                  styles.suggestionChip,
                  {
                    backgroundColor: t.surface,
                    borderColor: t.border,
                    opacity: pressed ? 0.7 : 1,
                  },
                ]}
              >
                <Text
                  style={[
                    styles.suggestionText,
                    {
                      color: t.text,
                    },
                  ]}
                >
                  {suggestion}
                </Text>
              </Pressable>
            ))}
          </ScrollView>
        </View>
      )}

      {/* Input */}
      <View
        style={[
          styles.inputContainer,
          {
            paddingBottom: Math.max(insets.bottom, 16),
            borderTopColor: t.border,
          },
        ]}
      >
        {(isRecording || isTranscribing) && (
          <View style={styles.voiceStatus} accessibilityLiveRegion="polite">
            {isRecording ? (
              <>
                <View style={styles.recordingDot} />
                <Text style={[styles.voiceStatusText, { color: t.risk }]}>
                  Recording {formatRecordingTime(recordingSeconds)} / 01:00 · Tap mic to stop
                </Text>
              </>
            ) : (
              <>
                <ActivityIndicator size="small" color={t.primary} />
                <Text style={[styles.voiceStatusText, { color: t.muted }]}>Transcribing…</Text>
              </>
            )}
          </View>
        )}

        <View style={styles.inputRow}>
          <TextInput
            autoFocus={Boolean(prefill)}
            value={chatInput}
            onChangeText={setChatInput}
            onSubmitEditing={() => sendMessage(chatInput)}
            returnKeyType="send"
            editable={!isTranscribing}
            placeholder="Add a task or ask anything..."
            placeholderTextColor={t.muted}
            style={[
              styles.input,
              {
                backgroundColor: t.surface,
                color: t.text,
                borderColor: t.border,
              },
            ]}
          />

          <Pressable
            onPress={isRecording ? transcribeRecording : startRecording}
            disabled={sending || isTranscribing}
            style={({ pressed }) => [
              styles.voiceButton,
              {
                backgroundColor: isRecording ? t.risk : t.surface2,
                opacity: pressed || sending || isTranscribing ? 0.65 : 1,
              },
            ]}
            accessibilityRole="button"
            accessibilityLabel={isRecording ? "Stop recording" : "Start voice input in English"}
            accessibilityState={{ disabled: sending || isTranscribing }}
          >
            <Mic size={18} color={isRecording ? "#FFFFFF" : t.text} />
          </Pressable>

          <Pressable
            onPress={() => sendMessage(chatInput)}
            disabled={!chatInput.trim() || sending || isRecording || isTranscribing}
            style={({ pressed }) => [
              styles.sendButton,
              {
                backgroundColor: chatInput.trim() ? t.primary : t.surface2,
                opacity: pressed ? 0.8 : 1,
              },
            ]}
            accessibilityLabel="Send"
            accessibilityState={{ disabled: !chatInput.trim() || sending || isRecording || isTranscribing }}
          >
            <Send
              size={17}
              color={chatInput.trim() ? "#FFFFFF" : t.muted}
            />
          </Pressable>
        </View>
        <Text style={[styles.voiceHint, { color: t.muted }]}>
          Voice input supports English · up to 60 seconds
        </Text>
      </View>
    </KeyboardAvoidingView>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },

  // Header
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 20,
    paddingBottom: 16,
    borderBottomWidth: 1,
  },

  backButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
  },

  aiIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
  },

  headerText: {
    justifyContent: "center",
  },

  title: {
    fontSize: 18,
    fontWeight: "600",
  },

  subtitle: {
    fontSize: 12,
    marginTop: 2,
  },

  // Messages
  messagesContainer: {
    flex: 1,
  },

  messagesContent: {
    paddingHorizontal: 20,
    paddingTop: 20,
    paddingBottom: 20,
    gap: 12,
  },

  messageRow: {
    width: "100%",
    flexDirection: "row",
  },

  userMessageRow: {
    justifyContent: "flex-end",
  },

  aiMessageRow: {
    justifyContent: "flex-start",
  },

  messageWrapper: {
    maxWidth: "85%",
  },

  messageBubble: {
    borderRadius: 16,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },

  messageText: {
    fontSize: 13.5,
    lineHeight: 20,
  },

  // Task reference
  taskReference: {
    marginTop: 6,
    width: "100%",
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 9,
    borderWidth: 1,
  },

  taskReferenceContent: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
  },

  taskReferenceTitle: {
    flex: 1,
    fontSize: 12.5,
    fontWeight: "500",
  },

  // Suggestions
  suggestionsContainer: {
    paddingHorizontal: 20,
  },

  suggestionsContent: {
    flexDirection: "row",
    gap: 8,
  },

  suggestionChip: {
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderWidth: 1,
  },

  suggestionText: {
    fontSize: 12,
  },

  // Input
  inputContainer: {
    flexDirection: "column",
    gap: 8,
    paddingHorizontal: 20,
    paddingTop: 16,
    borderTopWidth: 1,
  },

  inputRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },

  voiceStatus: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    minHeight: 20,
  },

  voiceStatusText: {
    fontSize: 12,
  },

  voiceHint: {
    fontSize: 10.5,
    paddingLeft: 2,
  },

  recordingDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: "#D92D20",
  },

  input: {
    flex: 1,
    minHeight: 46,
    borderRadius: 12,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 13.5,
  },

  sendButton: {
    width: 42,
    height: 42,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
  },

  voiceButton: {
    width: 42,
    height: 42,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
  },
})
