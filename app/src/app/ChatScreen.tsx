import { useEffect, useRef, useState } from "react"
import { useRouter, useLocalSearchParams } from "expo-router"
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native"
import { chatSuggestions } from "../data"
import { useSafeAreaInsets } from "react-native-safe-area-context"
import { useApp } from "../context/AppContext"
import type { ChatMessage } from "../data"
import { ChevronLeft, ChevronRight, Send, Sparkles } from "../components/icons"
import { apiFetch } from "../lib/apiClient"

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
  const scrollRef = useRef<ScrollView>(null)

  const sendMessage = async (text: string) => {
  const trimmed = text.trim()

  if (!trimmed || sending) return

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
        <TextInput
          autoFocus={Boolean(prefill)}
          value={chatInput}
          onChangeText={setChatInput}
          onSubmitEditing={() => sendMessage(chatInput)}
          returnKeyType="send"
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
          onPress={() => sendMessage(chatInput)}
          style={({ pressed }) => [
            styles.sendButton,
            {
              backgroundColor: chatInput.trim()
                ? t.primary
                : t.surface2,
              opacity: pressed ? 0.8 : 1,
            },
          ]}
          accessibilityLabel="Send"
        >
          <Send
            size={17}
            color={
              chatInput.trim()
                ? "#FFFFFF"
                : t.muted
            }
          />
        </Pressable>
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
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingHorizontal: 20,
    paddingTop: 16,
    borderTopWidth: 1,
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
})