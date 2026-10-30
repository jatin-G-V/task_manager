import { useCallback, useEffect, useMemo, useState } from "react"
import { useRouter, useLocalSearchParams } from "expo-router"
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native"
import { Ionicons } from "@expo/vector-icons"
import Constants from "expo-constants"
import { useSafeAreaInsets } from "react-native-safe-area-context"
import { useApp } from "../context/AppContext"
import { ChevronLeft } from "../components/icons"
import { apiFetch } from "../lib/apiClient"

const MIN_LEN = 10
const MAX_LEN = 500

type FeedbackType = "bug" | "suggestion" | "other"
type Quota = { used: number; limit: number; remaining: number }
type ContextMessage = { role: "user" | "assistant"; content: string }

const TYPES: { key: FeedbackType; label: string }[] = [
  { key: "bug", label: "Bug / wrong answer" },
  { key: "suggestion", label: "Suggestion" },
  { key: "other", label: "Other" },
]

// The chat screen may pass its last messages as a JSON string in `context`.
function parseContext(raw?: string): ContextMessage[] {
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed
      .filter(
        (item) =>
          item &&
          (item.role === "user" || item.role === "assistant") &&
          typeof item.content === "string" &&
          item.content.trim()
      )
      .slice(-6)
      .map((item) => ({ role: item.role, content: String(item.content).slice(0, 300) }))
  } catch {
    return []
  }
}

export default function FeedbackScreen() {
  const { t } = useApp()
  const router = useRouter()
  const insets = useSafeAreaInsets()
  const { context } = useLocalSearchParams<{ context?: string }>()

  const contextMessages = useMemo(() => parseContext(context), [context])

  const [quota, setQuota] = useState<Quota | null>(null)
  const [quotaError, setQuotaError] = useState(false)
  const [type, setType] = useState<FeedbackType>("bug")
  const [message, setMessage] = useState("")
  const [attach, setAttach] = useState(false)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sent, setSent] = useState(false)

  const loadQuota = useCallback(async () => {
    try {
      const result = await apiFetch("/feedback/quota")
      setQuota({
        used: Number(result.used ?? 0),
        limit: Number(result.limit ?? 2),
        remaining: Number(result.remaining ?? 0),
      })
      setQuotaError(false)
    } catch {
      setQuotaError(true)
    }
  }, [])

  useEffect(() => {
    void loadQuota()
  }, [loadQuota])

  const trimmedLength = message.trim().length
  const slotsLeft = quota ? quota.remaining > 0 : true
  const canSend = slotsLeft && trimmedLength >= MIN_LEN && !sending && !sent

  const submit = async () => {
    if (!canSend) return
    setSending(true)
    setError(null)

    try {
      const result = await apiFetch("/feedback", {
        method: "POST",
        body: JSON.stringify({
          type,
          message: message.trim(),
          include_context: attach && contextMessages.length > 0,
          context_messages: attach ? contextMessages : [],
          app_version: Constants.expoConfig?.version ?? undefined,
        }),
      })

      setQuota({
        used: Number(result.used ?? 0),
        limit: Number(result.limit ?? 2),
        remaining: Number(result.remaining ?? 0),
      })
      setSent(true)
      setTimeout(() => router.back(), 1400)
    } catch (err) {
      const text = err instanceof Error ? err.message : ""
      if (text.toLowerCase().includes("both feedback slots")) {
        setQuota((previous) => ({
          used: previous?.limit ?? 2,
          limit: previous?.limit ?? 2,
          remaining: 0,
        }))
      } else {
        setError(text || "Could not send feedback. Please try again.")
      }
    } finally {
      setSending(false)
    }
  }

  const quotaLabel = quota
    ? `${Math.min(quota.used, quota.limit)} of ${quota.limit} used this month`
    : quotaError
      ? "Could not load your monthly limit"
      : "Loading…"

  return (
    <KeyboardAvoidingView
      style={[styles.container, { backgroundColor: t.bg }]}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
      <View
        style={[
          styles.header,
          { paddingTop: insets.top + 12, borderBottomColor: t.border },
        ]}
      >
        <Pressable
          onPress={() => router.back()}
          style={({ pressed }) => [
            styles.backButton,
            { backgroundColor: t.surface, opacity: pressed ? 0.6 : 1 },
          ]}
          accessibilityLabel="Back"
        >
          <ChevronLeft size={18} color={t.muted} />
        </Pressable>

        <View>
          <Text style={[styles.title, { color: t.text }]}>Send feedback</Text>
          <Text style={[styles.subtitle, { color: t.muted }]}>{quotaLabel}</Text>
        </View>
      </View>

      <ScrollView
        contentContainerStyle={[
          styles.content,
          { paddingBottom: Math.max(insets.bottom, 16) + 24 },
        ]}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        {sent ? (
          <View style={[styles.notice, { backgroundColor: t.surface, borderColor: t.border }]}>
            <Ionicons name="checkmark-circle" size={22} color={t.primary} />
            <Text style={[styles.noticeText, { color: t.text }]}>
              Thank you. Your feedback was received.
            </Text>
          </View>
        ) : !slotsLeft ? (
          <View style={[styles.notice, { backgroundColor: t.surface, borderColor: t.border }]}>
            <Ionicons name="information-circle-outline" size={22} color={t.muted} />
            <Text style={[styles.noticeText, { color: t.text }]}>
              You've used both feedback slots this month. Thank you for the earlier notes! They reset on the 1st.
            </Text>
          </View>
        ) : (
          <>
            <Text style={[styles.label, { color: t.muted }]}>What is this about?</Text>
            <View style={styles.chips}>
              {TYPES.map((item) => {
                const active = type === item.key
                return (
                  <Pressable
                    key={item.key}
                    onPress={() => setType(item.key)}
                    style={[
                      styles.chip,
                      {
                        backgroundColor: active ? t.primary : t.surface,
                        borderColor: active ? t.primary : t.border,
                      },
                    ]}
                    accessibilityRole="button"
                    accessibilityState={{ selected: active }}
                  >
                    <Text
                      style={{
                        fontSize: 12.5,
                        color: active ? "#FFFFFF" : t.text,
                      }}
                    >
                      {item.label}
                    </Text>
                  </Pressable>
                )
              })}
            </View>

            <Text style={[styles.label, { color: t.muted, marginTop: 18 }]}>
              Tell us what happened or what you'd like
            </Text>
            <TextInput
              value={message}
              onChangeText={setMessage}
              multiline
              maxLength={MAX_LEN}
              textAlignVertical="top"
              placeholder="For example: I asked what to work on and it suggested a task that was already done."
              placeholderTextColor={t.muted}
              style={[
                styles.input,
                { backgroundColor: t.surface, borderColor: t.border, color: t.text },
              ]}
            />
            <Text
              style={[
                styles.counter,
                {
                  color:
                    trimmedLength > 0 && trimmedLength < MIN_LEN ? t.risk : t.muted,
                },
              ]}
            >
              {trimmedLength < MIN_LEN
                ? `At least ${MIN_LEN} characters (${trimmedLength}/${MIN_LEN})`
                : `${trimmedLength}/${MAX_LEN}`}
            </Text>

            {contextMessages.length > 0 && (
              <Pressable
                onPress={() => setAttach((value) => !value)}
                style={styles.checkRow}
                accessibilityRole="checkbox"
                accessibilityState={{ checked: attach }}
              >
                <Ionicons
                  name={attach ? "checkbox" : "square-outline"}
                  size={22}
                  color={attach ? t.primary : t.muted}
                />
                <Text style={[styles.checkText, { color: t.text }]}>
                  Attach my last chat messages so you can see what went wrong
                </Text>
              </Pressable>
            )}

            {error && (
              <Text style={[styles.errorText, { color: t.risk }]}>{error}</Text>
            )}

            <Pressable
              onPress={submit}
              disabled={!canSend}
              style={({ pressed }) => [
                styles.sendButton,
                {
                  backgroundColor: canSend ? t.primary : t.surface2,
                  opacity: pressed ? 0.85 : 1,
                },
              ]}
              accessibilityRole="button"
              accessibilityState={{ disabled: !canSend }}
            >
              {sending ? (
                <ActivityIndicator size="small" color="#FFFFFF" />
              ) : (
                <Text
                  style={{
                    fontSize: 14,
                    fontWeight: "600",
                    color: canSend ? "#FFFFFF" : t.muted,
                  }}
                >
                  Send feedback
                </Text>
              )}
            </Pressable>

            <Text style={[styles.hint, { color: t.muted }]}>
              You can send up to 2 per month. Feedback is optional and never shared publicly.
            </Text>
          </>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1 },

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
  title: { fontSize: 18, fontWeight: "600" },
  subtitle: { fontSize: 12, marginTop: 2 },

  content: { paddingHorizontal: 20, paddingTop: 20 },

  label: { fontSize: 12, marginBottom: 8 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    borderRadius: 999,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 7,
  },

  input: {
    minHeight: 130,
    borderRadius: 12,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 13.5,
    lineHeight: 20,
  },
  counter: { fontSize: 11, marginTop: 6, textAlign: "right" },

  checkRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginTop: 16,
  },
  checkText: { flex: 1, fontSize: 12.5, lineHeight: 18 },

  errorText: { fontSize: 12.5, marginTop: 14 },

  sendButton: {
    height: 46,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 20,
  },
  hint: { fontSize: 11, marginTop: 10, textAlign: "center" },

  notice: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 12,
    borderWidth: 1,
    borderRadius: 14,
    padding: 16,
  },
  noticeText: { flex: 1, fontSize: 13.5, lineHeight: 20 },
})