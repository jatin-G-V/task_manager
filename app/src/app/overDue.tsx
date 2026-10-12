import React, { useMemo, useState } from "react";
import {
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";

import { useApp } from "../context/AppContext";

import {
  AlertTriangle,
  Check,
  ChevronLeft,
  ChevronRight,
} from "../components/icons";

import type { Task } from "../types";
import { timingLabel } from "../utils/taskFormat";

type SectionFilter = "all" | Task["section"];

const filters: {
  value: SectionFilter;
  label: string;
}[] = [
  { value: "all", label: "All" },
  { value: "work", label: "Work" },
  { value: "personal", label: "Personal" },
  { value: "leisure", label: "Leisure" },
];

export default function OverdueScreen() {
  const { completeTask, t, overdueTasks } = useApp();
  const router = useRouter();
  const insets = useSafeAreaInsets();

  const [filter, setFilter] = useState<SectionFilter>("all");

  const visibleTasks = useMemo(
    () =>
      overdueTasks.filter(
        (task) => filter === "all" || task.section === filter
      ),
    [overdueTasks, filter]
  );

  const handleComplete = async (id: string) => {
    try {
      await completeTask(id);
    } catch (error) {
      console.error("Failed to complete task:", error);
      Alert.alert("Could not complete task", "Please try again.");
    }
  };

  return (
    <View
      style={[
        styles.container,
        {
          backgroundColor: t.bg,
        },
      ]}
    >
      {/* Header */}
      <View
        style={[
          styles.header,
          {
            paddingTop: insets.top + 16,
          },
        ]}
      >
        <Pressable
          onPress={() => router.back()}
          android_ripple={{ color: "transparent" }}
          style={({ pressed }) => [
            styles.backButton,
            pressed && styles.pressed,
          ]}
        >
          <ChevronLeft size={18} color={t.muted} />

          <Text
            style={[
              styles.backText,
              {
                color: t.muted,
              },
            ]}
          >
            Home
          </Text>
        </Pressable>

        <View style={styles.headerRow}>
          <View style={styles.headerContent}>
            <View style={styles.titleRow}>
              <AlertTriangle size={18} color={t.risk} />

              <Text
                style={[
                  styles.title,
                  {
                    color: t.text,
                    fontFamily: "DMSerifDisplay",
                  },
                ]}
              >
                Overdue tasks
              </Text>
            </View>

            <Text
              style={[
                styles.subtitle,
                {
                  color: t.muted,
                },
              ]}
            >
              Clear what slipped, one task at a time.
            </Text>
          </View>

          <View
            style={[
              styles.countBadge,
              {
                backgroundColor: t.riskBg,
              },
            ]}
          >
            <Text
              style={[
                styles.countText,
                {
                  color: t.risk,
                },
              ]}
            >
              {overdueTasks.length}
            </Text>
          </View>
        </View>
      </View>

      {/* Filters */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.filterScroll}
        contentContainerStyle={styles.filterContainer}
      >
        {filters.map((item) => {
          const selected = filter === item.value;

          return (
            <Pressable
              key={item.value}
              onPress={() => setFilter(item.value)}
              android_ripple={{ color: "transparent" }}
              style={({ pressed }) => [
                styles.filterButton,
                {
                  backgroundColor: selected ? t.risk : t.surface,
                  borderColor: selected ? t.risk : t.border,
                },
                pressed && styles.pressed,
              ]}
            >
              <Text
                style={[
                  styles.filterText,
                  {
                    color: selected ? "#FFFFFF" : t.muted,
                    fontWeight: selected ? "600" : "500",
                  },
                ]}
              >
                {item.label}
              </Text>
            </Pressable>
          );
        })}
      </ScrollView>

      {/* Content */}
      {visibleTasks.length === 0 ? (
        <View style={styles.emptyContainer}>
          <View
            style={[
              styles.emptyIcon,
              {
                backgroundColor: t.successBg,
              },
            ]}
          >
            <Check size={20} color={t.success} />
          </View>

          <Text
            style={[
              styles.emptyTitle,
              {
                color: t.text,
              },
            ]}
          >
            Nothing overdue here
          </Text>

          <Text
            style={[
              styles.emptySubtitle,
              {
                color: t.muted,
              },
            ]}
          >
            You’re all caught up in this section.
          </Text>
        </View>
      ) : (
        <ScrollView
          style={styles.list}
          contentContainerStyle={[
            styles.listContent,
            {
              paddingBottom: insets.bottom + 24,
            },
          ]}
          showsVerticalScrollIndicator={false}
        >
          {visibleTasks.map((task) => (
            <View
              key={task.id}
              style={[
                styles.taskCard,
                {
                  backgroundColor: t.surface,
                  borderColor: t.border,
                },
              ]}
            >
              {/* Task Header */}
              <Pressable
                onPress={() =>
                  router.push({
                    pathname: "/task-details",
                    params: {
                      id: task.id,
                      section: task.section,
                    },
                  })
                }
                android_ripple={{ color: "transparent" }}
                style={({ pressed }) => [
                  styles.taskHeader,
                  pressed && styles.pressed,
                ]}
              >
                <View
                  style={[
                    styles.taskIcon,
                    {
                      backgroundColor: t.riskBg,
                    },
                  ]}
                >
                  <AlertTriangle size={15} color={t.risk} />
                </View>

                <View style={styles.taskInfo}>
                  <Text
                    numberOfLines={2}
                    style={[
                      styles.taskTitle,
                      {
                        color: t.text,
                      },
                    ]}
                  >
                    {task.title}
                  </Text>

                  <Text
                    numberOfLines={1}
                    style={[
                      styles.taskTiming,
                      {
                        color: t.risk,
                      },
                    ]}
                  >
                    {task.section} · {timingLabel(task).text}
                  </Text>
                </View>

                <ChevronRight size={15} color={t.muted} />
              </Pressable>

              {/* Actions */}
              <View
                style={[
                  styles.actions,
                  {
                    borderTopColor: t.border,
                  },
                ]}
              >
                <Pressable
                  onPress={() => void handleComplete(task.id)}
                  android_ripple={{ color: "transparent" }}
                  style={({ pressed }) => [
                    styles.actionButton,
                    {
                      backgroundColor: t.successBg,
                    },
                    pressed && styles.pressed,
                  ]}
                >
                  <Check size={12} color={t.success} />

                  <Text
                    style={[
                      styles.actionText,
                      {
                        color: t.success,
                      },
                    ]}
                  >
                    Complete
                  </Text>
                </Pressable>

                <Pressable
                  onPress={() =>
                    router.push({
                      pathname: "/ChatScreen",
                      params: {
                        prefill: `Reschedule ${task.title} to `,
                      },
                    })
                  }
                  android_ripple={{ color: "transparent" }}
                  style={({ pressed }) => [
                    styles.actionButton,
                    {
                      backgroundColor: t.riskBg,
                    },
                    pressed && styles.pressed,
                  ]}
                >
                  <Text
                    style={[
                      styles.actionText,
                      {
                        color: t.risk,
                      },
                    ]}
                  >
                    Reschedule
                  </Text>
                </Pressable>
              </View>
            </View>
          ))}
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },

  header: {
    paddingHorizontal: 20,
    paddingBottom: 12,
  },

  backButton: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    gap: 6,
    marginBottom: 12,
  },

  backText: {
    fontSize: 13,
  },

  headerRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
    gap: 16,
  },

  headerContent: {
    flex: 1,
  },

  titleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },

  title: {
    fontSize: 23,
    lineHeight: 29,
  },

  subtitle: {
    fontSize: 12.5,
    marginTop: 3,
  },

  countBadge: {
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },

  countText: {
    fontSize: 11,
    fontWeight: "600",
  },

  filterScroll: {
    flexGrow: 0,
  },

  filterContainer: {
    paddingHorizontal: 20,
    paddingVertical: 12,
    gap: 8,
  },

  filterButton: {
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },

  filterText: {
    fontSize: 11.5,
  },

  list: {
    flex: 1,
  },

  listContent: {
    paddingHorizontal: 20,
    gap: 10,
  },

  taskCard: {
    borderWidth: 1,
    borderRadius: 16,
    padding: 14,
  },

  taskHeader: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 12,
  },

  taskIcon: {
    width: 36,
    height: 36,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },

  taskInfo: {
    flex: 1,
    minWidth: 0,
  },

  taskTitle: {
    fontSize: 14,
    fontWeight: "600",
    lineHeight: 19,
  },

  taskTiming: {
    fontSize: 10.5,
    marginTop: 3,
    textTransform: "capitalize",
  },

  actions: {
    flexDirection: "row",
    gap: 8,
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
  },

  actionButton: {
    flex: 1,
    minHeight: 34,
    borderRadius: 8,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    paddingHorizontal: 8,
  },

  actionText: {
    fontSize: 11.5,
    fontWeight: "600",
  },

  emptyContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingBottom: 64,
    paddingHorizontal: 20,
  },

  emptyIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 12,
  },

  emptyTitle: {
    fontSize: 15,
    fontWeight: "600",
  },

  emptySubtitle: {
    fontSize: 12.5,
    marginTop: 3,
    textAlign: "center",
  },

  pressed: {
    opacity: 0.6,
  },
});