import { useEffect, useRef, useState } from "react"
import { Pressable, Text, View } from "react-native"
import { Ionicons } from "@expo/vector-icons"
import * as Clipboard from "expo-clipboard"

export type Reason = "wrong_task" | "wrong_time" | "not_helpful" | "other"

type Props = {
  text: string
  vote?: "up" | "down"
  reason?: Reason
  onVote: (value: "up" | "down") => void
  onReason: (reason: Reason) => void
  color: string
  mutedColor: string
  surfaceColor: string
  borderColor: string
  activeColor: string
}

const REASONS: { key: Reason; label: string }[] = [
  { key: "wrong_task", label: "Wrong task" },
  { key: "wrong_time", label: "Wrong time" },
  { key: "not_helpful", label: "Not helpful" },
]

export default function MessageActions({
  text,
  vote,
  reason,
  onVote,
  onReason,
  color,
  mutedColor,
  surfaceColor,
  borderColor,
  activeColor,
}: Props) {
  const [copied, setCopied] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current)
  }, [])

  const copy = async () => {
    try {
      await Clipboard.setStringAsync(text)
      setCopied(true)
      if (timer.current) clearTimeout(timer.current)
      timer.current = setTimeout(() => setCopied(false), 1500)
    } catch {
      // Copy is a convenience action; don't interrupt chat for clipboard errors.
    }
  }

  const iconButton = {
    width: 34,
    height: 30,
    alignItems: "center" as const,
    justifyContent: "center" as const,
  }

  return (
    <View style={{ marginTop: 6, alignSelf: "flex-start" }}>
      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          backgroundColor: surfaceColor,
          borderWidth: 1,
          borderColor,
          borderRadius: 16,
          paddingHorizontal: 6,
        }}
      >
        <Pressable
          onPress={copy}
          hitSlop={6}
          style={iconButton}
          accessibilityRole="button"
          accessibilityLabel="Copy reply"
        >
          <Ionicons
            name={copied ? "checkmark" : "copy-outline"}
            size={17}
            color={copied ? activeColor : mutedColor}
          />
        </Pressable>

        <Pressable
          onPress={() => onVote("up")}
          hitSlop={6}
          style={iconButton}
          accessibilityRole="button"
          accessibilityLabel="Helpful"
        >
          <Ionicons
            name={vote === "up" ? "thumbs-up" : "thumbs-up-outline"}
            size={17}
            color={vote === "up" ? activeColor : mutedColor}
          />
        </Pressable>

        <Pressable
          onPress={() => onVote("down")}
          hitSlop={6}
          style={iconButton}
          accessibilityRole="button"
          accessibilityLabel="Not helpful"
        >
          <Ionicons
            name={vote === "down" ? "thumbs-down" : "thumbs-down-outline"}
            size={17}
            color={vote === "down" ? activeColor : mutedColor}
          />
        </Pressable>
      </View>

      {vote === "down" && !reason && (
        <View style={{ flexDirection: "row", gap: 8, marginTop: 6, flexWrap: "wrap" }}>
          {REASONS.map((item) => (
            <Pressable
              key={item.key}
              onPress={() => onReason(item.key)}
              style={{
                paddingVertical: 4,
                paddingHorizontal: 10,
                borderRadius: 12,
                backgroundColor: surfaceColor,
                borderWidth: 1,
                borderColor,
              }}
            >
              <Text style={{ fontSize: 12, color }}>{item.label}</Text>
            </Pressable>
          ))}
        </View>
      )}
    </View>
  )
}