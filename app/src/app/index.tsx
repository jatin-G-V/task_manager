import React, { useState } from 'react'
import {
  View,
  Text,
  ScrollView,
  Pressable,
  TextInput,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
} from 'react-native'
import { useRouter } from 'expo-router'
import { SafeAreaView } from 'react-native-safe-area-context'
import { useApp } from '../context/AppContext'
import BottomTabBar from '../components/BottomTabBar'
import FAB from '../components/FAB'

import {
  ChevronRight,
  Sparkles,
  UserCircle,
  Send,
} from '../components/icons'

import type { ChatMessage } from '../data'
import {
  chatSuggestions,
  getAIResponse,
} from '../data'

export default function DashboardScreen() {
  const {
    t,
    user,
    dueTodayCount,
    atRiskCount,
    suggestedTask,
    tasks,
  } = useApp()

  const router = useRouter()

  const [chatInput, setChatInput] = useState('')

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'init',
      role: 'ai',
      text: 'Good morning, Jatin. You have a busy day — let me know what you need help with.',
    },
  ])

  const [chatActive, setChatActive] = useState(false)

  // --------------------------------
  // AI CHAT
  // --------------------------------

  const sendMessage = (text: string) => {
    if (!text.trim()) return

    const userMsg: ChatMessage = {
      id: `u${Date.now()}`,
      role: 'user',
      text,
    }

    const response = getAIResponse(text, tasks)

    const aiMsg: ChatMessage = {
      id: `a${Date.now()}`,
      role: 'ai',
      text: response.text,
      taskRef: response.taskRef,
    }

    setMessages((prev) => [
      ...prev,
      userMsg,
      aiMsg,
    ])

    setChatInput('')
    setChatActive(true)
  }

  // --------------------------------
  // DATE
  // --------------------------------

  const dayOfWeek = new Date().toLocaleDateString(
    'en-US',
    {
      weekday: 'long',
    }
  )

  const dateStr = new Date().toLocaleDateString(
    'en-US',
    {
      month: 'long',
      day: 'numeric',
    }
  )

  // --------------------------------
  // UI
  // --------------------------------

  return (
    <KeyboardAvoidingView
      style={[
        styles.container,
        {
          backgroundColor: t.bg,
        },
      ]}
      behavior={
        Platform.OS === 'ios'
          ? 'padding'
          : undefined
      }
    >

      {/* ================================ */}
      {/* TOP CONTENT */}
      {/* ================================ */}

      <SafeAreaView style={styles.mainContent}>

        {/* HEADER */}

        <View style={styles.header}>
          <View style={styles.headerTextContainer}>

            <Text
              style={[
                styles.greeting,
                {
                  color: t.text,
                },
              ]}
            >
              Good morning,{' '}
              {user.name
                ? user.name.split(' ')[0]
                : 'there'}
            </Text>

            <Text
              style={[
                styles.date,
                {
                  color: t.muted,
                },
              ]}
            >
              {dayOfWeek}, {dateStr}
            </Text>

          </View>

          <Pressable
            onPress={() => router.push('/menu')}
            style={({ pressed }) => [
              styles.profileButton,
              {
                backgroundColor: t.surface,
                borderColor: t.border,
              },
              pressed && styles.pressed,
            ]}
          >
            <UserCircle
              size={22}
              color={t.muted}
            />
          </Pressable>
        </View>


        {/* ================================ */}
        {/* DAILY DIGEST */}
        {/* ================================ */}

        <View
          style={[
            styles.digestCard,
            {
              backgroundColor: t.surface,
              borderColor: t.border,
            },
          ]}
        >

          <View style={styles.digestContent}>

            {/* Due today */}

            <View style={styles.digestItem}>

              <View
                style={[
                  styles.statusDot,
                  {
                    backgroundColor: t.due,
                  },
                ]}
              />

              <Text
                style={[
                  styles.digestText,
                  {
                    color: t.text,
                  },
                ]}
              >
                <Text
                  style={[
                    styles.digestNumber,
                    {
                      color: t.due,
                    },
                  ]}
                >
                  {dueTodayCount}
                </Text>{' '}
                due today
              </Text>

            </View>


            {/* Divider */}

            <View
              style={[
                styles.digestDivider,
                {
                  backgroundColor: t.border,
                },
              ]}
            />


            {/* At risk */}

            <View style={styles.digestItem}>

              <View
                style={[
                  styles.statusDot,
                  {
                    backgroundColor: t.risk,
                  },
                ]}
              />

              <Text
                style={[
                  styles.digestText,
                  {
                    color: t.text,
                  },
                ]}
              >
                <Text
                  style={[
                    styles.digestNumber,
                    {
                      color: t.risk,
                    },
                  ]}
                >
                  {atRiskCount}
                </Text>{' '}
                at risk
              </Text>

            </View>

          </View>

          <ChevronRight
            size={16}
            color={t.muted}
          />

        </View>


        {/* ================================ */}
        {/* SUGGESTED FOCUS */}
        {/* ================================ */}

        {suggestedTask && (
          <Pressable
            onPress={() =>
              router.push({
                pathname: '../components/TaskDetail',
                params: {
                  taskId: suggestedTask.id,
                },
              })
            }
            style={({ pressed }) => [
              styles.suggestedCard,
              {
                backgroundColor: `${t.primary}12`,
                borderColor: `${t.primary}30`,
              },
              pressed && styles.pressed,
            ]}
          >

            <View style={styles.suggestedHeader}>

              <Sparkles
                size={14}
                color={t.primary}
              />

              <Text
                style={[
                  styles.suggestedLabel,
                  {
                    color: t.primary,
                  },
                ]}
              >
                Suggested Focus
              </Text>

            </View>


            <Text
              style={[
                styles.suggestedTitle,
                {
                  color: t.text,
                },
              ]}
            >
              {suggestedTask.title}
            </Text>


            <View style={styles.suggestedFooter}>

              <Text
                style={[
                  styles.deadline,
                  {
                    color: t.muted,
                  },
                ]}
              >
                {suggestedTask.deadline}
              </Text>

              <Text
                style={[
                  styles.openText,
                  {
                    color: t.primary,
                  },
                ]}
              >
                Tap to open →
              </Text>

            </View>

          </Pressable>
        )}


        {/* ================================ */}
        {/* AI ASSISTANT */}
        {/* ================================ */}

        <View
          style={[
            styles.aiCard,
            {
              backgroundColor: t.surface,
              borderColor: t.border,
            },
          ]}
        >

          {/* AI HEADER */}

          <View
            style={[
              styles.aiHeader,
              {
                borderBottomColor: t.border,
              },
            ]}
          >

            <View style={styles.aiHeaderLeft}>

              <View
                style={[
                  styles.aiIcon,
                  {
                    backgroundColor: t.primary,
                  },
                ]}
              >
                <Sparkles
                  size={13}
                  color="#FFFFFF"
                />
              </View>

              <Text
                style={[
                  styles.aiTitle,
                  {
                    color: t.text,
                  },
                ]}
              >
                AI Assistant
              </Text>

            </View>


            <View style={styles.onlineContainer}>

              <View
                style={[
                  styles.onlineDot,
                  {
                    backgroundColor: t.success,
                  },
                ]}
              />

              <Text
                style={[
                  styles.onlineText,
                  {
                    color: t.muted,
                  },
                ]}
              >
                Online
              </Text>

            </View>

          </View>


          {/* ================================ */}
          {/* MESSAGE AREA */}
          {/* ================================ */}

          <ScrollView
            style={styles.messagesScroll}
            contentContainerStyle={styles.messagesContainer}
            showsVerticalScrollIndicator={false}
            keyboardShouldPersistTaps="handled"
          >

            {messages.map((msg) => (

              <View
                key={msg.id}
                style={[
                  styles.messageRow,
                  msg.role === 'user'
                    ? styles.userMessageRow
                    : styles.aiMessageRow,
                ]}
              >

                <View
                  style={styles.messageWrapper}
                >

                  <View
                    style={[
                      styles.messageBubble,
                      {
                        backgroundColor:
                          msg.role === 'user'
                            ? t.primary
                            : t.surface2,
                      },
                    ]}
                  >

                    <Text
                      style={[
                        styles.messageText,
                        {
                          color:
                            msg.role === 'user'
                              ? '#FFFFFF'
                              : t.text,
                        },
                      ]}
                    >
                      {msg.text}
                    </Text>

                  </View>


                  {/* TASK REFERENCE */}

                  {msg.taskRef && (
                    <Pressable
                      onPress={() =>
                        router.push({
                          pathname:
                            '../components/TaskDetail',
                          params: {
                            taskId:
                              msg.taskRef!.id,
                          },
                        })
                      }
                      style={[
                        styles.taskReference,
                        {
                          backgroundColor:
                            t.surface,
                          borderColor:
                            t.border,
                        },
                      ]}
                    >

                      <View
                        style={
                          styles.taskReferenceTop
                        }
                      >

                        <Text
                          numberOfLines={1}
                          style={[
                            styles.taskReferenceTitle,
                            {
                              color: t.text,
                            },
                          ]}
                        >
                          {msg.taskRef.title}
                        </Text>

                        <ChevronRight
                          size={13}
                          color={t.muted}
                        />

                      </View>

                      <Text
                        style={[
                          styles.taskReferenceDeadline,
                          {
                            color: t.muted,
                          },
                        ]}
                      >
                        {msg.taskRef.deadline}
                      </Text>

                    </Pressable>
                  )}

                </View>

              </View>

            ))}

          </ScrollView>


          {/* ================================ */}
          {/* SUGGESTIONS */}
          {/* ================================ */}

          {!chatActive && (
            <View
              style={styles.suggestionsContainer}
            >

              {chatSuggestions.map(
                (suggestion) => (

                  <Pressable
                    key={suggestion}
                    onPress={() =>
                      sendMessage(suggestion)
                    }
                    style={({ pressed }) => [
                      styles.suggestionChip,
                      {
                        backgroundColor:
                          t.surface2,
                        borderColor:
                          t.border,
                      },
                      pressed &&
                        styles.pressed,
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

                )
              )}

            </View>
          )}


          {/* ================================ */}
          {/* INPUT */}
          {/* ================================ */}

          <View
            style={[
              styles.inputContainer,
              {
                borderTopColor: t.border,
              },
            ]}
          >

            <TextInput
              value={chatInput}
              onChangeText={setChatInput}
              onSubmitEditing={() =>
                sendMessage(chatInput)
              }
              returnKeyType="send"
              placeholder="Ask anything about your tasks…"
              placeholderTextColor={t.muted}
              style={[
                styles.chatInput,
                {
                  backgroundColor: t.surface2,
                  color: t.text,
                },
              ]}
            />

            <Pressable
              onPress={() =>
                sendMessage(chatInput)
              }
              style={({ pressed }) => [
                styles.sendButton,
                {
                  backgroundColor:
                    chatInput.trim()
                      ? t.primary
                      : t.surface2,
                },
                pressed && styles.pressed,
              ]}
            >

              <Send
                size={16}
                color={
                  chatInput.trim()
                    ? '#FFFFFF'
                    : t.muted
                }
              />

            </Pressable>

          </View>

        </View>

      </SafeAreaView>


      {/* ================================ */}
      {/* BOTTOM NAVIGATION */}
      {/* ================================ */}

      <BottomTabBar />

      <FAB />

    </KeyboardAvoidingView>
  )
}


/* ========================================= */
/* STYLES */
/* ========================================= */

const styles = StyleSheet.create({

  container: {
    flex: 1,
  },

  /*
   * This is the important part.
   * Everything above the bottom nav lives
   * inside this flex container.
   */
  mainContent: {
    flex: 1,
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 8,
  },


  /* ================================ */
  /* HEADER */
  /* ================================ */

  header: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    marginBottom: 16,
  },

  headerTextContainer: {
    flex: 1,
  },

  greeting: {
    fontSize: 22,
    fontWeight: '700',
    fontFamily: 'DM Serif Display',
  },

  date: {
    fontSize: 13,
    marginTop: 2,
    fontFamily: 'Outfit',
  },

  profileButton: {
    width: 38,
    height: 38,
    borderRadius: 19,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
  },


  /* ================================ */
  /* DAILY DIGEST */
  /* ================================ */

  digestCard: {
    width: '100%',

    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',

    paddingHorizontal: 16,
    paddingVertical: 14,

    borderRadius: 16,
    borderWidth: 1,

    marginBottom: 16,
  },

  digestContent: {
    flexDirection: 'row',
    alignItems: 'center',
  },

  digestItem: {
    flexDirection: 'row',
    alignItems: 'center',
  },

  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 6,
  },

  digestText: {
    fontSize: 13,
    fontWeight: '500',
  },

  digestNumber: {
    fontWeight: '700',
  },

  digestDivider: {
    width: 1,
    height: 16,
    marginHorizontal: 16,
  },


  /* ================================ */
  /* SUGGESTED FOCUS */
  /* ================================ */

  suggestedCard: {
    width: '100%',

    padding: 16,

    borderRadius: 16,
    borderWidth: 1.5,

    marginBottom: 16,
  },

  suggestedHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },

  suggestedLabel: {
    marginLeft: 6,
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },

  suggestedTitle: {
    fontSize: 15,
    fontWeight: '600',
    lineHeight: 20,
    marginBottom: 6,
  },

  suggestedFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },

  deadline: {
    fontSize: 12,
  },

  openText: {
    fontSize: 12,
    fontWeight: '500',
  },


  /* ================================ */
  /* AI CARD */
  /* ================================ */

  aiCard: {
    flex: 1,

    width: '100%',

    borderRadius: 18,
    borderWidth: 1,

    overflow: 'hidden',

    /*
     * This is what makes the assistant
     * consume the remaining screen.
     */
    minHeight: 0,
  },


  /* ================================ */
  /* AI HEADER */
  /* ================================ */

  aiHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',

    paddingHorizontal: 16,
    paddingTop: 14,
    paddingBottom: 12,

    borderBottomWidth: 1,
  },

  aiHeaderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
  },

  aiIcon: {
    width: 30,
    height: 30,

    borderRadius: 15,

    alignItems: 'center',
    justifyContent: 'center',

    marginRight: 9,
  },

  aiTitle: {
    fontSize: 14,
    fontWeight: '600',
  },

  onlineContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },

  onlineDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    marginRight: 6,
  },

  onlineText: {
    fontSize: 12,
  },


  /* ================================ */
  /* MESSAGE AREA */
  /* ================================ */

  messagesScroll: {
    flex: 1,
    minHeight: 0,
  },

  messagesContainer: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 16,
  },

  messageRow: {
    width: '100%',
    marginBottom: 12,
  },

  aiMessageRow: {
    alignItems: 'flex-start',
  },

  userMessageRow: {
    alignItems: 'flex-end',
  },

  messageWrapper: {
    maxWidth: '85%',
  },

  messageBubble: {
    borderRadius: 17,

    paddingHorizontal: 14,
    paddingVertical: 11,
  },

  messageText: {
    fontSize: 13.5,
    lineHeight: 20,
    fontFamily: 'Outfit',
  },


  /* ================================ */
  /* TASK REFERENCE */
  /* ================================ */

  taskReference: {
    width: '100%',

    marginTop: 6,

    borderRadius: 12,

    paddingHorizontal: 12,
    paddingVertical: 8,

    borderWidth: 1,
  },

  taskReferenceTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },

  taskReferenceTitle: {
    flex: 1,

    fontSize: 12.5,
    fontWeight: '500',

    marginRight: 6,
  },

  taskReferenceDeadline: {
    fontSize: 11.5,
    marginTop: 2,
  },


  /* ================================ */
  /* SUGGESTIONS */
  /* ================================ */

  suggestionsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',

    paddingHorizontal: 16,
    paddingBottom: 10,

    gap: 8,
  },

  suggestionChip: {
    paddingHorizontal: 12,
    paddingVertical: 7,

    borderRadius: 999,

    borderWidth: 1,
  },

  suggestionText: {
    fontSize: 12,
    fontFamily: 'Outfit',
  },


  /* ================================ */
  /* INPUT */
  /* ================================ */

  inputContainer: {
    flexDirection: 'row',
    alignItems: 'center',

    paddingHorizontal: 12,
    paddingVertical: 10,

    gap: 8,

    borderTopWidth: 1,
  },

  chatInput: {
    flex: 1,

    height: 42,

    borderRadius: 12,

    paddingHorizontal: 13,
    paddingVertical: 8,

    fontSize: 13.5,
    fontFamily: 'Outfit',
  },

  sendButton: {
    width: 38,
    height: 38,

    borderRadius: 12,

    alignItems: 'center',
    justifyContent: 'center',
  },


  /* ================================ */
  /* PRESS */
  /* ================================ */

  pressed: {
    opacity: 0.7,
  },

})