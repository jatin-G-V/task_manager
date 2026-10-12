import React, { useMemo } from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useApp } from "../context/AppContext";
import { useRouter } from 'expo-router';
import {
  ChevronLeft,
  ChevronRight,
  AlertTriangle,
  Clock,
  Sparkles,
} from "../components/icons";
import { timingLabel } from "../utils/taskFormat";

export default function DailyDigestScreen() {
  const router = useRouter();
  const {
    t,
    tasks,
    suggestedTask,
  } = useApp();

  const allTasks = useMemo(
    () => [
      ...tasks.work,
      ...tasks.personal,
      ...tasks.leisure,
    ],
    [tasks],
  );

  const dueTodayTasks = allTasks.filter(
    (task) => task.dueToday,
  );

  const atRiskTasks = allTasks.filter(
    (task) => task.atRisk,
  );

  const dateStr = new Date().toLocaleDateString(
    "en-US",
    {
      weekday: "long",
      month: "long",
      day: "numeric",
    },
  );

  return (
    <SafeAreaView edges={['top']}
      style={[
        styles.container,
        {
          backgroundColor: t.bg,
        },
      ]}
    >
      {/* Header */}
      <View style={styles.header}>
        <Pressable
          onPress={() => router.back()}
          style={({ pressed }) => [
            styles.backButton,
            pressed && styles.pressed,
          ]}
        >
          <ChevronLeft
            size={18}
            color={t.muted}
          />

          <Text
            style={[
              styles.backText,
              {
                color: t.muted,
              },
            ]}
          >
            Back
          </Text>
        </Pressable>

        <Text
          style={[
            styles.title,
            {
              color: t.text,
              fontFamily: "DMSerifDisplay",
            },
          ]}
        >
          Daily Digest
        </Text>

        <Text
          style={[
            styles.date,
            {
              color: t.muted,
            },
          ]}
        >
          {dateStr}
        </Text>
      </View>

      {/* Content */}
      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        {/* Due Today */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <View
              style={[
                styles.dot,
                {
                  backgroundColor: t.due,
                },
              ]}
            />

            <Text
              style={[
                styles.sectionTitle,
                {
                  color: t.muted,
                },
              ]}
            >
              DUE TODAY
            </Text>

            <View
              style={[
                styles.countBadge,
                {
                  backgroundColor: t.dueBg,
                },
              ]}
            >
              <Text
                style={[
                  styles.countText,
                  {
                    color: t.due,
                  },
                ]}
              >
                {dueTodayTasks.length}
              </Text>
            </View>
          </View>

          {dueTodayTasks.length === 0 ? (
            <Text
              style={[
                styles.emptyText,
                {
                  color: t.muted,
                },
              ]}
            >
              Nothing due today
            </Text>
          ) : (
            <View style={styles.taskList}>
              {dueTodayTasks.map((task) => (
                <Pressable
                  key={task.id}
                  onPress={() =>
                    router.push(`/task-details?id=${task.id}&section=${task.section}`)
                  }
                  style={({ pressed }) => [
                    styles.taskCard,
                    {
                      backgroundColor: t.surface,
                      borderColor: t.border,
                    },
                    pressed && styles.cardPressed,
                  ]}
                >
                  <View style={styles.taskContent}>
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

                    <View style={styles.timingRow}>
                      <Clock
                        size={12}
                        color={t.due}
                      />

                      <Text
                        numberOfLines={1}
                        style={[
                          styles.timingText,
                          {
                            color: t.due,
                          },
                        ]}
                      >
                        {timingLabel(task).text}
                      </Text>
                    </View>
                  </View>

                  <ChevronRight
                    size={15}
                    color={t.muted}
                  />
                </Pressable>
              ))}
            </View>
          )}
        </View>

        {/* At Risk */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <View
              style={[
                styles.dot,
                {
                  backgroundColor: t.risk,
                },
              ]}
            />

            <Text
              style={[
                styles.sectionTitle,
                {
                  color: t.muted,
                },
              ]}
            >
              AT RISK
            </Text>

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
                {atRiskTasks.length}
              </Text>
            </View>
          </View>

          {atRiskTasks.length === 0 ? (
            <Text
              style={[
                styles.emptyText,
                {
                  color: t.muted,
                },
              ]}
            >
              Nothing at risk
            </Text>
          ) : (
            <View style={styles.taskList}>
              {atRiskTasks.map((task) => (
                <Pressable
                  key={task.id}
                  onPress={() =>
                    router.push(`/task-details?id=${task.id}&section=${task.section}`)
                  }
                  style={({ pressed }) => [
                    styles.riskCard,
                    {
                      backgroundColor: t.riskBg,
                      borderColor: `${t.risk}40`,
                    },
                    pressed && styles.cardPressed,
                  ]}
                >
                  <View style={styles.taskContent}>
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

                    <View style={styles.timingRow}>
                      <AlertTriangle
                        size={12}
                        color={t.risk}
                      />

                      <Text
                        numberOfLines={1}
                        style={[
                          styles.timingText,
                          {
                            color: t.risk,
                          },
                        ]}
                      >
                        {timingLabel(task).text}
                      </Text>
                    </View>
                  </View>

                  <View
                    style={[
                      styles.urgentBadge,
                      {
                        backgroundColor: `${t.risk}20`,
                      },
                    ]}
                  >
                    <Text
                      style={[
                        styles.urgentText,
                        {
                          color: t.risk,
                        },
                      ]}
                    >
                      URGENT
                    </Text>
                  </View>
                </Pressable>
              ))}
            </View>
          )}
        </View>

        {/* Suggested Focus */}
        {suggestedTask && (
          <View style={styles.section}>
            <View style={styles.sectionHeader}>
              <Sparkles
                size={13}
                color={t.primary}
              />

              <Text
                style={[
                  styles.sectionTitle,
                  {
                    color: t.muted,
                  },
                ]}
              >
                SUGGESTED FOCUS
              </Text>
            </View>

            <Pressable
              onPress={() =>
                router.push(`/task-details?id=${suggestedTask.id}&section=${suggestedTask.section}`)
              }
              style={({ pressed }) => [
                styles.suggestedCard,
                {
                  backgroundColor: `${t.primary}10`,
                  borderColor: `${t.primary}35`,
                },
                pressed && styles.cardPressed,
              ]}
            >
              <Text
                numberOfLines={2}
                style={[
                  styles.suggestedTitle,
                  {
                    color: t.text,
                  },
                ]}
              >
                {suggestedTask.title}
              </Text>

              {suggestedTask.priorityWhy && (
                <Text
                  numberOfLines={3}
                  style={[
                    styles.priorityWhy,
                    {
                      color: t.muted,
                    },
                  ]}
                >
                  {suggestedTask.priorityWhy}
                </Text>
              )}

              <View style={styles.suggestedFooter}>
                <Text
                  numberOfLines={1}
                  style={[
                    styles.suggestedTiming,
                    {
                      color: t.muted,
                    },
                  ]}
                >
                  {timingLabel(suggestedTask).text}
                </Text>

                <Text
                  style={[
                    styles.openTask,
                    {
                      color: t.primary,
                    },
                  ]}
                >
                  Open task →
                </Text>
              </View>
            </Pressable>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
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
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    gap: 6,
    marginBottom: 16,
  },

  backText: {
    fontSize: 14,
  },

  title: {
    fontSize: 24,
    lineHeight: 30,
    fontWeight: "700",
  },

  date: {
    fontSize: 13,
    marginTop: 2,
  },

  scrollView: {
    flex: 1,
  },

  content: {
    paddingHorizontal: 20,
    paddingBottom: 32,
  },

  section: {
    marginBottom: 24,
  },

  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginBottom: 12,
  },

  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },

  sectionTitle: {
    fontSize: 13,
    fontWeight: "600",
    letterSpacing: 0.9,
  },

  countBadge: {
    marginLeft: "auto",
    minWidth: 26,
    borderRadius: 999,
    paddingHorizontal: 8,
    paddingVertical: 2,
    alignItems: "center",
  },

  countText: {
    fontSize: 12,
    fontWeight: "600",
  },

  emptyText: {
    fontSize: 14,
    paddingLeft: 8,
  },

  taskList: {
    gap: 10,
  },

  taskCard: {
    minHeight: 66,
    borderWidth: 1,
    borderRadius: 16,
    paddingHorizontal: 16,
    paddingVertical: 14,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },

  taskContent: {
    flex: 1,
    minWidth: 0,
    marginRight: 12,
  },

  taskTitle: {
    fontSize: 14.5,
    fontWeight: "500",
    lineHeight: 19,
  },

  timingRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginTop: 4,
  },

  timingText: {
    flex: 1,
    fontSize: 12,
    fontWeight: "500",
  },

  riskCard: {
    minHeight: 66,
    borderWidth: 1.5,
    borderRadius: 16,
    paddingHorizontal: 16,
    paddingVertical: 14,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },

  urgentBadge: {
    borderRadius: 999,
    paddingHorizontal: 8,
    paddingVertical: 5,
  },

  urgentText: {
    fontSize: 11,
    fontWeight: "600",
  },

  suggestedCard: {
    borderWidth: 1.5,
    borderRadius: 16,
    padding: 16,
  },

  suggestedTitle: {
    fontSize: 15,
    fontWeight: "600",
    lineHeight: 20,
    marginBottom: 6,
  },

  priorityWhy: {
    fontSize: 13,
    lineHeight: 19,
    marginBottom: 8,
  },

  suggestedFooter: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
  },

  suggestedTiming: {
    flex: 1,
    fontSize: 12,
  },

  openTask: {
    fontSize: 12,
    fontWeight: "600",
  },

  pressed: {
    opacity: 0.6,
  },

  cardPressed: {
    transform: [{ scale: 0.985 }],
    opacity: 0.9,
  },
});
