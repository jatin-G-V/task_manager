import { useEffect, useState } from "react"
import { useRouter } from "expo-router"
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
import { useSafeAreaInsets } from "react-native-safe-area-context"
import { useApp } from "../context/AppContext"
import { ChevronLeft } from "../components/icons"
import { apiFetch } from "../lib/apiClient"

const MAX_CHARS = 300

const EXAMPLES = [
  "Short and to the point",
  "Friendly and encouraging",
  "Mix of English and Hinglish, casual",
  "Calm and professional",
]

export default function AiStyleScreen() {
  const { t } = useApp()
  const router = useRouter()
  const insets = useSafeAreaInsets()

  const [note, setNote] = useState("")
  const [saved, setSaved] = useState("")
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    apiFetch("/settings/style")
      .then((result) => {
        if (!active) return
        const value = typeof result.style_note === "string" ? result.style_note : ""
        setNote(value)
        setSaved(value)
      })
      .catch(() => active && setError("Could not load your saved style."))
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [])

  const dirty = note.trim() !== saved.trim()

  const save = async (value: string) => {
    setSaving(true)
    setError(null)
    setMessage(null)
    try {
      const result = await apiFetch("/settings/style", {
        method: "PUT",
        body: JSON.stringify({ style_note: value }),
      })
      const stored = typeof result.style_note === "string" ? result.style_note : ""
      setNote(stored)
      setSaved(stored)
      setMessage(stored ? "Saved. New replies will follow this style." : "Cleared. Replies are back to default.")
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Could not save. Please try again.")
    } finally {
      setSaving(false)
    }
  }

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
          <Text style={[styles.title, { color: t.text }]}>Reply style</Text>
          <Text style={[styles.subtitle, { color: t.muted }]}>
            How should the assistant talk to you?
          </Text>
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
        {loading ? (
          <ActivityIndicator color={t.primary} />
        ) : (
          <>
            <TextInput
              value={note}
              onChangeText={setNote}
              multiline
              maxLength={MAX_CHARS}
              textAlignVertical="top"
              placeholder="For example: keep it short, friendly, and call me Jatin."
              placeholderTextColor={t.muted}
              style={[
                styles.input,
                { backgroundColor: t.surface, borderColor: t.border, color: t.text },
              ]}
            />
            <Text style={[styles.counter, { color: t.muted }]}>
              {note.length}/{MAX_CHARS}
            </Text>

            <Text style={[styles.label, { color: t.muted }]}>Quick ideas</Text>
            <View style={styles.chips}>
              {EXAMPLES.map((example) => (
                <Pressable
                  key={example}
                  onPress={() => setNote(example)}
                  style={[styles.chip, { backgroundColor: t.surface, borderColor: t.border }]}
                >
                  <Text style={{ fontSize: 12, color: t.text }}>{example}</Text>
                </Pressable>
              ))}
            </View>

            {message && <Text style={[styles.info, { color: t.primary }]}>{message}</Text>}
            {error && <Text style={[styles.info, { color: t.risk }]}>{error}</Text>}

            <Pressable
              onPress={() => save(note)}
              disabled={!dirty || saving}
              style={({ pressed }) => [
                styles.saveButton,
                {
                  backgroundColor: dirty && !saving ? t.primary : t.surface2,
                  opacity: pressed ? 0.85 : 1,
                },
              ]}
            >
              {saving ? (
                <ActivityIndicator size="small" color="#FFFFFF" />
              ) : (
                <Text
                  style={{
                    fontSize: 14,
                    fontWeight: "600",
                    color: dirty ? "#FFFFFF" : t.muted,
                  }}
                >
                  Save style
                </Text>
              )}
            </Pressable>

            {saved ? (
              <Pressable onPress={() => save("")} disabled={saving} style={styles.clearButton}>
                <Text style={{ fontSize: 13, color: t.muted }}>Clear and use the default</Text>
              </Pressable>
            ) : null}

            <Text style={[styles.hint, { color: t.muted }]}>
              This only changes how replies sound. It never changes what the assistant does, and
              questions that need your decision (like delete confirmations) stay exactly as they are.
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
  input: {
    minHeight: 120,
    borderRadius: 12,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 13.5,
    lineHeight: 20,
  },
  counter: { fontSize: 11, marginTop: 6, textAlign: "right" },
  label: { fontSize: 12, marginTop: 14, marginBottom: 8 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    borderRadius: 999,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 7,
  },
  info: { fontSize: 12.5, marginTop: 14 },
  saveButton: {
    height: 46,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 18,
  },
  clearButton: { alignItems: "center", paddingVertical: 14 },
  hint: { fontSize: 11, lineHeight: 16, marginTop: 6, textAlign: "center" },
})