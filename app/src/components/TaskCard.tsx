import React from "react";
import {
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { useApp } from "../context/AppContext";
import { useRouter } from "expo-router";
import type { Task } from "../types";
import {
  effortLabel,
  recurrenceLabel,
  timingLabel,
  urgencyLabel,
} from "../utils/taskFormat";
import { Clock } from "./icons";
// import { View } from "react-native/Libraries/Components/View/View";

interface Props {
  task: Task;
  variant?: Task["section"];
  completed?: boolean;
  onTap?: () => void;
}

export default function TaskCard({
  task,
  variant,
  completed = false,
  onTap,
}: Props) {
  const { t } = useApp();
  const router = useRouter();

  const section = variant ?? task.section;

  const timing = timingLabel(task);
  const recurrence = recurrenceLabel(task);
  const urgency = urgencyLabel(task.urgency, t);
  const effort = effortLabel(task.effort);


  const handleTap = () => {
    if (onTap) {
      onTap();
    } else {
      router.push(`/task-details?id=${task.id}&section=${task.section}`);
    }
  };

  const isRisk =
    timing.tone === "overdue" || task.atRisk;

  return (
    <Pressable
      onPress={handleTap}
      android_ripple={{ color: "transparent" }}
      style={[
        styles.card,
        {
          backgroundColor: t.surface,
          borderColor: t.border,
          opacity: completed ? 0.65 : 1,
        },
      ]}
    >
      {/* Title */}
      <Text
        numberOfLines={2}
        style={[
          styles.title,
          {
            color: completed
              ? t.muted
              : t.text,
            fontSize:
              section === "leisure"
                ? 14
                : 14.5,
            textDecorationLine: completed
              ? "line-through"
              : "none",
          },
        ]}
      >
        {task.title}
      </Text>



      {/* Timing */}
      <View style={styles.timingRow}>
        <Clock
          size={12}
          color={isRisk ? t.risk : t.muted}
        />

        <Text
          numberOfLines={1}
          style={[
            styles.timingText,
            {
              color: isRisk
                ? t.risk
                : t.muted,

              fontWeight:
                timing.tone === "overdue"
                  ? "600"
                  : "400",
            },
          ]}
        >
          {timing.text}
        </Text>
      </View>

      {/* Urgency + Effort */}
      {!completed && (urgency || effort || task.isBlocked || recurrence) && (
        <View style={styles.metadataRow}>
          {recurrence && (
            <View
              style={[
                styles.recurrenceChip,
                { backgroundColor: t.surface2 },
              ]}
            >
              <Text
                numberOfLines={1}
                style={[styles.recurrenceText, { color: t.primary }]}
              >
                {recurrence}
              </Text>
            </View>
          )}
          {/* Urgency */}
          {urgency && (
            <View
              style={[
                styles.urgencyChip,
                {
                  backgroundColor:
                    urgency.bg,
                },
              ]}
            >
              <View
                style={[
                  styles.urgencyDot,
                  {
                    backgroundColor:
                      urgency.color,
                  },
                ]}
              />

              <Text
                style={[
                  styles.urgencyText,
                  {
                    color:
                      urgency.color,
                  },
                ]}
              >
                {urgency.text}
              </Text>
            </View>
          )}

          {/* Effort */}
          {effort && (
            <View
              style={[
                styles.effortChip,
                {
                  backgroundColor:
                    t.surface2,
                },
              ]}
            >
              <Text
                style={[
                  styles.effortText,
                  {
                    color:
                      effort.color,
                  },
                ]}
              >
                {effort.text}
              </Text>
            </View>
          )}
          {/* Blocked */}
          {task.isBlocked && (
            <View
              style={[
                styles.blockedChip,
                {
                  backgroundColor: t.surface2,
                  borderColor: t.border,
                },
              ]}
            >
              <Text
                style={[
                  styles.blockedText,
                  {
                    color: t.risk,
                  },
                ]}
              >
                Blocked
              </Text>
            </View>
            )}
        </View>
      )}

    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    width: "100%",
    borderWidth: 1,
    borderRadius: 16,
    paddingHorizontal: 16,
    paddingVertical: 14,
  },

  title: {
    fontWeight: "600",
    lineHeight: 19,
  },


  timingRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginTop: 8,
  },

  timingText: {
    flex: 1,
    fontSize: 11.5,
  },

  metadataRow: {
    flexDirection: "row",
    alignItems: "center",
    flexWrap: "wrap",
    gap: 6,
    marginTop: 10,
  },

  recurrenceChip: {
    maxWidth: "100%",
    borderRadius: 999,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },

  recurrenceText: {
    fontSize: 10.5,
    fontWeight: "600",
  },

  urgencyChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    borderRadius: 999,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },

  urgencyDot: {
    width: 5,
    height: 5,
    borderRadius: 2.5,
  },

  urgencyText: {
    fontSize: 10.5,
    fontWeight: "700",
  },

  blockedChip: {
  borderRadius: 999,
  paddingHorizontal: 8,
  paddingVertical: 4,
  borderWidth: 1,
},

blockedText: {
  fontSize: 9.5,
  fontWeight: "600",
},

  effortChip: {
    borderRadius: 999,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },

  effortText: {
    fontSize: 9.5,
    fontWeight: "500",
  },




});
