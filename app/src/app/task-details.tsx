import React, { useRef, useState } from "react";
import {
  Alert,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import DateTimePicker from "@react-native-community/datetimepicker";
import { useApp } from "../context/AppContext";
import { useLocalSearchParams, useRouter } from 'expo-router';
import {
  Calendar,
  Check,
  ChevronLeft,
  Pencil,
  Sparkles,
  X,
} from "../components/icons";
import { SafeAreaView } from "react-native-safe-area-context";
import {
  parseInstant,
  recurrenceRuleParts,
  recurrenceLabel,
  timingLabel,
} from "../utils/taskFormat";
import type { Effort, Task, Urgency } from "../types";
type DatePickerMode = "date" | "time" | null;
type DatePickerTarget =
  | "scheduled-date"
  | "scheduled-start"
  | "scheduled-end"
  | "deadline-date"
  | "deadline-time";
const urgencyOptions: Exclude<Urgency, null>[] = [
  "low",
  "medium",
  "high",
  "urgent",
];
const effortOptions: Exclude<Effort, null>[] = [
  "low",
  "medium",
  "high",
];
const weekDays = [
  { short: "Mon", full: "Monday" },
  { short: "Tue", full: "Tuesday" },
  { short: "Wed", full: "Wednesday" },
  { short: "Thu", full: "Thursday" },
  { short: "Fri", full: "Friday" },
  { short: "Sat", full: "Saturday" },
  { short: "Sun", full: "Sunday" },
];
type RecurrenceKind =
  | "none"
  | "daily"
  | "weekly"
  | "monthly"
  | "custom";
type RecurrenceEndMode = "never" | "date";
const combineLocalDateTime = (
  date: Date,
  time?: Date,
) => {
  const result = new Date(date);
  if (time) {
    result.setHours(
      time.getHours(),
      time.getMinutes(),
      0,
      0,
    );
  } else {
    result.setHours(12, 0, 0, 0);
  }
  return result;
};
function recurrenceKind(task: Task): RecurrenceKind {
  if (!task.isRecurring || !task.recurrence) {
    return "none";
  }
  const rule = recurrenceRuleParts(task.recurrence);
  if (!rule || rule.interval !== 1) return "custom";
  const supportedFields = new Set(["FREQ", "INTERVAL", "BYDAY"]);
  if (Object.keys(rule.fields).some((field) => !supportedFields.has(field))) {
    return "custom";
  }
  if (rule.frequency === "DAILY") return "daily";
  if (rule.frequency === "MONTHLY") return "monthly";
  if (rule.frequency === "WEEKLY") return "weekly";
  return "custom";
}
function recurrenceDays(task: Task) {
  const rule = recurrenceRuleParts(task.recurrence);
  if (rule?.frequency !== "WEEKLY") return [];
  const value = rule.days;
  if (value.length === 0) {
    const anchor = parseInstant(task.scheduledStart ?? task.deadline);
    if (!anchor) return [];
    const weekdayCode = ["SU", "MO", "TU", "WE", "TH", "FR", "SA"][anchor.getDay()];
    value.push(weekdayCode);
  }
  return weekDays
    .filter((day) =>
      value.includes(day.short.toUpperCase()),
    )
    .map((day) => day.full);
}
function weeklyRule(days: string[]) {
  if (days.length === 1) {
    return `weekly on ${days[0]}`;
  }
  if (days.length === 2) {
    return `weekly on ${days[0]} and ${days[1]}`;
  }
  return `weekly on ${days
    .slice(0, -1)
    .join(", ")} and ${days.at(-1)}`;
}
export default function TaskDetailScreen() {
  const { id, section } = useLocalSearchParams<{ id: string; section: Task['section'] }>();
  const router = useRouter();
  const {
    tasks,
    completeTask,
    t,
    updateTask,
    darkMode,
  } = useApp();
  const task = tasks[section]?.find((item) => item.id === id);
  const [editingTitle, setEditingTitle] =
    useState(false);
  const [title, setTitle] = useState(
    task?.title ?? "",
  );
  const [editingNotes, setEditingNotes] =
    useState(false);
  const [notes, setNotes] = useState(
    task?.brief ?? "",
  );
  const [recurrenceEditorOpen, setRecurrenceEditorOpen] =
    useState(false);
  const [pickerMode, setPickerMode] =
    useState<DatePickerMode>(null);
  const [pickerTarget, setPickerTarget] =
    useState<DatePickerTarget | null>(null);
  const [pickerValue, setPickerValue] =
    useState(new Date());
  const notesAtEditStart = useRef(
    task?.brief ?? "",
  );
  if (!task) {
    return null;
  }
  const scheduleStart =
    parseInstant(task.scheduledStart);
  const scheduleEnd =
    parseInstant(task.scheduledEnd);
  const deadline =
    parseInstant(task.deadline);
  const timing = timingLabel(task);
  const repeat = recurrenceLabel(task);
  const save = async (
    updates: Parameters<typeof updateTask>[2],
  ) => {
    try {
      await updateTask(task.id, task.section, updates);
    } catch (error) {
      console.error('Failed to update task:', error);
      Alert.alert('Could not save changes', 'Please try again.');
    }
  };
  const rejectPast = (date: Date) => {
    if (date.getTime() <= Date.now()) {
      Alert.alert(
        "Invalid time",
        "Please choose a date and time in the future.",
      );
      return true;
    }
    return false;
  };
  /*
   * DATE / TIME PICKER
   */
  const openScheduledDatePicker = () => {
    setPickerValue(
      scheduleStart ??
        scheduleEnd ??
        new Date(),
    );
    setPickerTarget("scheduled-date");
    setPickerMode("date");
  };
  const openScheduledStartPicker = () => {
    setPickerValue(
      scheduleStart ?? new Date(),
    );
    setPickerTarget("scheduled-start");
    setPickerMode("time");
  };
  const openScheduledEndPicker = () => {
    setPickerValue(
      scheduleEnd ?? new Date(),
    );
    setPickerTarget("scheduled-end");
    setPickerMode("time");
  };
  const openDeadlineDatePicker = () => {
    setPickerValue(
      deadline ?? new Date(),
    );
    setPickerTarget("deadline-date");
    setPickerMode("date");
  };
  const openDeadlineTimePicker = () => {
    setPickerValue(
      deadline ?? new Date(),
    );
    setPickerTarget("deadline-time");
    setPickerMode("time");
  };
  const closePicker = () => {
    setPickerMode(null);
    setPickerTarget(null);
  };
  const confirmPicker = () => {
    if (!pickerTarget) return closePicker();
    const target = pickerTarget;
    const selected = pickerValue;
    closePicker();
    switch (target) {
      case "scheduled-date":
        handleScheduledDateChange(selected);
        break;
      case "scheduled-start":
        handleScheduledStartChange(selected);
        break;
      case "scheduled-end":
        handleScheduledEndChange(selected);
        break;
      case "deadline-date":
        handleDeadlineDateChange(selected);
        break;
      case "deadline-time":
        handleDeadlineTimeChange(selected);
        break;
    }
  };
  const handleScheduledDateChange = (
    date: Date,
  ) => {
    if (rejectPast(date)) return;
    const nextStart = scheduleStart
      ? combineLocalDateTime(
          date,
          scheduleStart,
        )
      : combineLocalDateTime(date);
    const nextEnd = scheduleEnd
      ? combineLocalDateTime(
          date,
          scheduleEnd,
        )
      : null;
    if (
      nextStart &&
      nextEnd &&
      nextEnd <= nextStart
    ) {
      Alert.alert(
        "Invalid time",
        "End time must be after the start time.",
      );
      return;
    }
    const updates: Parameters<
      typeof updateTask
    >[2] = {
      deadline: null,
      scheduleType: "scheduled",
    };
    if (scheduleStart) {
      updates.scheduledStart =
        nextStart.toISOString();
    }
    if (scheduleEnd) {
      updates.scheduledEnd =
        nextEnd!.toISOString();
    }
    if (!scheduleStart && !scheduleEnd) {
      updates.scheduledStart =
        nextStart.toISOString();
      updates.hasExplicitTime = false;
    }
    save(updates);
  };
  const handleScheduledStartChange = (
    time: Date,
  ) => {
    if (!scheduleStart && !scheduleEnd) {
      Alert.alert(
        "Set date first",
        "Set the date before adding a start time.",
      );
      return;
    }
    const baseDate =
      scheduleStart ??
      scheduleEnd ??
      new Date();
    const nextStart =
      combineLocalDateTime(
        baseDate,
        time,
      );
    const end = scheduleEnd;
    if (end && end <= nextStart) {
      Alert.alert(
        "Invalid time",
        "Start time must be before the end time.",
      );
      return;
    }
    save({
      deadline: null,
      scheduleType: "scheduled",
      scheduledStart:
        nextStart.toISOString(),
      hasExplicitTime: true,
    });
  };
  const handleScheduledEndChange = (
    time: Date,
  ) => {
    if (!scheduleStart && !scheduleEnd) {
      Alert.alert(
        "Set date first",
        "Set the date before adding an end time.",
      );
      return;
    }
    const baseDate =
      scheduleStart ??
      scheduleEnd ??
      new Date();
    const nextEnd =
      combineLocalDateTime(
        baseDate,
        time,
      );
    if (
      scheduleStart &&
      nextEnd <= scheduleStart
    ) {
      Alert.alert(
        "Invalid time",
        "End time must be after the start time.",
      );
      return;
    }
    save({
      deadline: null,
      scheduleType: "scheduled",
      scheduledEnd:
        nextEnd.toISOString(),
      hasExplicitTime: true,
    });
  };
  const handleDeadlineDateChange = (
    date: Date,
  ) => {
    const nextDeadline =
      combineLocalDateTime(
        date,
        task.hasExplicitTime
          ? deadline ?? undefined
          : undefined,
      );
    if (rejectPast(nextDeadline)) return;
    save({
      scheduleType: "flexible",
      deadline:
        nextDeadline.toISOString(),
      scheduledStart: null,
      scheduledEnd: null,
      hasExplicitTime:
        Boolean(
          task.hasExplicitTime &&
            deadline,
        ),
    });
  };
  const handleDeadlineTimeChange = (
    time: Date,
  ) => {
    if (!deadline) {
      Alert.alert(
        "Set date first",
        "Set the date before adding a time.",
      );
      return;
    }
    const nextDeadline =
      combineLocalDateTime(
        deadline,
        time,
      );
    if (rejectPast(nextDeadline)) return;
    save({
      scheduleType: "flexible",
      deadline:
        nextDeadline.toISOString(),
      scheduledStart: null,
      scheduledEnd: null,
      hasExplicitTime: true,
    });
  };
  const askAI = () => {
  router.push({
    pathname: "/ChatScreen",
    params: {
      prefill: `About "${task.title}" (${timing.text}): `,
    },
  });
};
  const handleComplete = async () => {
    try {
      await completeTask(task.id);
      router.replace('/');
    } catch (error) {
      console.error('Failed to complete task:', error);
      Alert.alert('Could not complete task', 'Please try again.');
    }
  };
  const formatDate = (
    value: Date | null,
  ) => {
    if (!value) return "Select date";
    return value.toLocaleDateString(
      "en-US",
      {
        weekday: "short",
        month: "short",
        day: "numeric",
      },
    );
  };
  const formatTime = (
    value: Date | null,
  ) => {
    if (!value) return "Set time";
    return value.toLocaleTimeString(
      "en-US",
      {
        hour: "numeric",
        minute: "2-digit",
      },
    );
  };
  return (
    <SafeAreaView edges = {['top']}
      style={[
        styles.container,
        {
          backgroundColor: t.bg,
        },
      ]}
    >
      {/* HEADER */}
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
            {task.section}
          </Text>
        </Pressable>
        {editingTitle ? (
          <View style={styles.titleEditRow}>
            <TextInput
              autoFocus
              value={title}
              onChangeText={setTitle}
              onBlur={() => {
                const nextTitle =
                  title.trim();
                if (
                  nextTitle &&
                  nextTitle !== task.title
                ) {
                  save({
                    title: nextTitle,
                  });
                }
                setEditingTitle(false);
              }}
              style={[
                styles.titleInput,
                {
                  backgroundColor:
                    t.surface,
                  borderColor:
                    t.primary,
                  color: t.text,
                },
              ]}
            />
          </View>
        ) : (
          <Pressable
            onPress={() => {
              setTitle(task.title);
              setEditingTitle(true);
            }}
            style={styles.titleButton}
          >
            <Text
              style={[
                styles.title,
                {
                  color: t.text,
                  fontFamily:
                    "DMSerifDisplay",
                },
              ]}
            >
              {task.title}
            </Text>
            <Pencil
              size={13}
              color={t.muted}
            />
          </Pressable>
        )}
      </View>
      {/* CONTENT */}
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={
          styles.scrollContent
        }
        showsVerticalScrollIndicator={false}
      >
        {/* TIMING */}
        <InfoCard>
          <View style={styles.cardHeader}>
            <Calendar
              size={14}
              color={t.muted}
            />
            <Text
              style={[
                styles.cardTitle,
                {
                  color: t.text,
                },
              ]}
            >
              {task.scheduleType ===
              "scheduled"
                ? "When"
                : "Do before"}
            </Text>
          </View>
          <View
            style={[
              styles.timingSummary,
              {
                backgroundColor:
                  timing.tone === "overdue"
                    ? t.riskBg
                    : t.surface2,
              },
            ]}
          >
            <Text
              style={[
                styles.timingSummaryText,
                {
                  color:
                    timing.tone ===
                    "overdue"
                      ? t.risk
                      : t.text,
                },
              ]}
            >
              {timing.text}
            </Text>
          </View>
          {task.scheduleType ===
          "scheduled" ? (
            <>
              <EditRow label="Date">
                <Pressable
                  onPress={
                    openScheduledDatePicker
                  }
                >
                  <Text
                    style={[
                      styles.valueText,
                      {
                        color: t.text,
                      },
                    ]}
                  >
                    {formatDate(
                      scheduleStart ??
                        scheduleEnd,
                    )}
                  </Text>
                </Pressable>
              </EditRow>
              <EditRow label="Start time">
                <Pressable
                  onPress={
                    openScheduledStartPicker
                  }
                >
                  <Text
                    style={[
                      styles.valueText,
                      {
                        color:
                          task.hasExplicitTime
                            ? t.text
                            : t.muted,
                      },
                    ]}
                  >
                    {task.hasExplicitTime
                      ? formatTime(
                          scheduleStart,
                        )
                      : "Set time"}
                  </Text>
                </Pressable>
              </EditRow>
              <EditRow label="End time">
                <View
                  style={
                    styles.valueRow
                  }
                >
                  <Pressable
                    onPress={
                      openScheduledEndPicker
                    }
                  >
                    <Text
                      style={[
                        styles.valueText,
                        {
                          color:
                            scheduleEnd
                              ? t.text
                              : t.muted,
                        },
                      ]}
                    >
                      {formatTime(
                        scheduleEnd,
                      )}
                    </Text>
                  </Pressable>
                  {task.scheduledEnd && (
                    <Pressable
                      onPress={() =>
                        save({
                          scheduledEnd:
                            null,
                        })
                      }
                    >
                      <Text
                        style={[
                          styles.clearText,
                          {
                            color: t.risk,
                          },
                        ]}
                      >
                        Clear
                      </Text>
                    </Pressable>
                  )}
                </View>
              </EditRow>
            </>
          ) : (
            <>
              <EditRow label="Date">
                <View
                  style={
                    styles.valueRow
                  }
                >
                  <Pressable
                    onPress={
                      openDeadlineDatePicker
                    }
                  >
                    <Text
                      style={[
                        styles.valueText,
                        {
                          color:
                            deadline
                              ? t.text
                              : t.muted,
                        },
                      ]}
                    >
                      {formatDate(
                        deadline,
                      )}
                    </Text>
                  </Pressable>
                  {task.deadline && (
                    <Pressable
                      onPress={() =>
                        save({
                          deadline: null,
                          hasExplicitTime:
                            false,
                        })
                      }
                    >
                      <Text
                        style={[
                          styles.clearText,
                          {
                            color: t.risk,
                          },
                        ]}
                      >
                        Clear
                      </Text>
                    </Pressable>
                  )}
                </View>
              </EditRow>
              <EditRow label="Time">
                <View
                  style={
                    styles.valueRow
                  }
                >
                  <Pressable
                    onPress={
                      openDeadlineTimePicker
                    }
                  >
                    <Text
                      style={[
                        styles.valueText,
                        {
                          color:
                            task.hasExplicitTime
                              ? t.text
                              : t.muted,
                        },
                      ]}
                    >
                      {task.hasExplicitTime
                        ? formatTime(
                            deadline,
                          )
                        : "Set time"}
                    </Text>
                  </Pressable>
                  {task.hasExplicitTime && (
                    <Pressable
                      onPress={() => {
                        if (!deadline)
                          return;
                        const next =
                          combineLocalDateTime(
                            deadline,
                          );
                        if (
                          rejectPast(next)
                        )
                          return;
                        save({
                          deadline:
                            next.toISOString(),
                          hasExplicitTime:
                            false,
                        });
                      }}
                    >
                      <Text
                        style={[
                          styles.clearText,
                          {
                            color: t.risk,
                          },
                        ]}
                      >
                        Clear
                      </Text>
                    </Pressable>
                  )}
                </View>
              </EditRow>
            </>
          )}
        </InfoCard>
        {/* URGENCY / EFFORT */}
        <InfoCard>
          <SegmentedRow
            label="Urgency"
            options={urgencyOptions}
            selected={
              task.urgency ?? null
            }
            onSelect={(value) =>
              save({
                urgency:
                  task.urgency === value
                    ? null
                    : value,
              })
            }
          />
          <View style={{ height: 14 }} />
          <SegmentedRow
            label="Effort"
            options={effortOptions}
            selected={
              task.effort ?? null
            }
            onSelect={(value) =>
              save({
                effort:
                  task.effort === value
                    ? null
                    : value,
              })
            }
          />
        </InfoCard>
        {/* RECURRENCE */}
        {task.isRecurring && (
          <InfoCard>
          <View
            style={styles.recurrenceHeader}
          >
            <Text
              style={[
                styles.smallLabel,
                {
                  color: t.muted,
                },
              ]}
            >
              REPEATS
            </Text>
            <Pressable
              onPress={() =>
                setRecurrenceEditorOpen(
                  true,
                )
              }
              style={[
                styles.editButton,
                {
                  backgroundColor:
                    t.surface2,
                },
              ]}
            >
              <Pencil
                size={10}
                color={t.primary}
              />
              <Text
                style={[
                  styles.editButtonText,
                  {
                    color: t.primary,
                  },
                ]}
              >
                Edit
              </Text>
            </Pressable>
          </View>
          <Pressable
            onPress={() =>
              setRecurrenceEditorOpen(true)
            }
          >
            <View style={styles.repeatRow}>
              <Text
                style={[
                  styles.repeatText,
                  {
                    color: repeat
                      ? t.text
                      : t.muted,
                  },
                ]}
              >
                {repeat ??
                  "Does not repeat"}
              </Text>
              {task.recurrenceEnd &&
                parseInstant(
                  task.recurrenceEnd,
                ) && (
                  <Text
                    style={[
                      styles.repeatEnd,
                      {
                        color: t.muted,
                      },
                    ]}
                  >
                    until{" "}
                    {parseInstant(
                      task.recurrenceEnd,
                    )!.toLocaleDateString(
                      "en-US",
                      {
                        month: "short",
                        day: "numeric",
                      },
                    )}
                  </Text>
                )}
            </View>
          </Pressable>
        </InfoCard>
              )}
        {/* NOTES */}

          <InfoCard>
            <View
              style={styles.notesHeader}
            >
              <Text
                style={[
                  styles.cardTitle,
                  {
                    color: t.text,
                  },
                ]}
              >
                Notes
              </Text>
              {!editingNotes && (
                <Pencil
                  size={12}
                  color={t.muted}
                />
              )}
            </View>
            {editingNotes ? (
              <TextInput
                autoFocus
                value={notes}
                onChangeText={setNotes}
                multiline
                textAlignVertical="top"
                onBlur={() => {
                  if (
                    notes !==
                    notesAtEditStart.current
                  ) {
                    save({
                      brief: notes,
                    });
                  }
                  setEditingNotes(false);
                }}
                style={[
                  styles.notesInput,
                  {
                    backgroundColor:
                      t.surface2,
                    color: t.text,
                    borderColor:
                      t.border,
                  },
                ]}
              />
            ) : (
              <Pressable
                onPress={() => {
                  notesAtEditStart.current =
                    task.brief ?? "";
                  setNotes(
                    task.brief ?? "",
                  );
                  setEditingNotes(true);
                }}
              >
                <Text
                  style={[
                    styles.notesText,
                    {
                      color: task.brief
                        ? t.text
                        : t.muted,
                    },
                  ]}
                >
                  {task.brief ||
                    "Add notes"}
                </Text>
              </Pressable>
            )}
          </InfoCard>

      </ScrollView>
      {/* COMPLETE */}
      <View
        style={[
          styles.footer,
          {
            borderTopColor: t.border,
            backgroundColor:
              t.surface,
          },
        ]}
      >
        <Pressable
          onPress={askAI}
          style={[
            styles.askAIButton,
            {
              backgroundColor: t.surface2,
              borderColor: t.border,
            },
          ]}
        >
          <Sparkles
            size={16}
            color={t.primary}
          />
          <Text
            style={[
              styles.askAIText,
              {
                color: t.primary,
              },
            ]}
          >
            Ask AI about this task
          </Text>
        </Pressable>
        <Pressable
          onPress={handleComplete}
          style={({ pressed }) => [
            styles.completeButton,
            {
              backgroundColor: t.success,
            },
            pressed &&
              styles.completePressed,
          ]}
        >
          <Check
            size={18}
            color="#FFFFFF"
          />
          <Text
            style={styles.completeText}
          >
            Mark Complete
          </Text>
        </Pressable>
      </View>
      {/* DATE / TIME PICKER */}
      <Modal
        visible={Boolean(pickerMode)}
        transparent
        animationType="fade"
        onRequestClose={closePicker}
      >
        <View style={styles.pickerOverlay}>
          <View
            style={[
              styles.pickerSheet,
              {
                backgroundColor: t.surface,
                borderColor: t.border,
              },
            ]}
          >
            <Text style={[styles.pickerTitle, { color: t.text }]}>
              {pickerMode === "date" ? "Choose a date" : "Choose a time"}
            </Text>
            {pickerMode && (
              <DateTimePicker
                value={pickerValue}
                mode={pickerMode}
                display="spinner"
                themeVariant={darkMode ? "dark" : "light"}
                textColor={t.text}
                onValueChange={(_, selectedDate) => {
                  if (selectedDate) setPickerValue(selectedDate);
                }}
                onDismiss={closePicker}
              />
            )}
            <View style={styles.pickerActions}>
              <Pressable
                onPress={closePicker}
                style={[styles.pickerAction, { borderColor: t.border }]}
              >
                <Text style={[styles.pickerCancelText, { color: t.muted }]}>Cancel</Text>
              </Pressable>
              <Pressable
                onPress={confirmPicker}
                style={[styles.pickerAction, { backgroundColor: t.primary, borderColor: t.primary }]}
              >
                <Text style={styles.pickerConfirmText}>Done</Text>
              </Pressable>
            </View>
          </View>
        </View>
      </Modal>
      {/* RECURRENCE EDITOR */}
      <RecurrenceEditor
        visible={recurrenceEditorOpen}
        task={task}
        onClose={() =>
          setRecurrenceEditorOpen(false)
        }
        onSave={(updates) => {
          save(updates);
          setRecurrenceEditorOpen(false);
        }}
      />
    </SafeAreaView>
  );
}
/* -------------------------------------------------------------------------- */
/* INFO CARD                                                                  */
/* -------------------------------------------------------------------------- */
function InfoCard({
  children,
}: {
  children: React.ReactNode;
}) {
  const { t } = useApp();
  return (
    <View
      style={[
        styles.infoCard,
        {
          backgroundColor: t.surface,
          borderColor: t.border,
        },
      ]}
    >
      {children}
    </View>
  );
}
/* -------------------------------------------------------------------------- */
/* EDIT ROW                                                                   */
/* -------------------------------------------------------------------------- */
function EditRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  const { t } = useApp();
  return (
    <View
      style={[
        styles.editRow,
        {
          backgroundColor: t.surface2,
        },
      ]}
    >
      <Text
        style={[
          styles.editLabel,
          {
            color: t.muted,
          },
        ]}
      >
        {label}
      </Text>
      {children}
    </View>
  );
}
/* -------------------------------------------------------------------------- */
/* SEGMENTED ROW                                                              */
/* -------------------------------------------------------------------------- */
function SegmentedRow<T extends string>({
  label,
  options,
  selected,
  onSelect,
}: {
  label: string;
  options: readonly T[];
  selected: T | null;
  onSelect: (value: T) => void;
}) {
  const { t } = useApp();
  return (
    <View>
      <Text
        style={[
          styles.smallLabel,
          {
            color: t.muted,
          },
        ]}
      >
        {label.toUpperCase()}
      </Text>
      <View style={styles.segmentRow}>
        {options.map((option) => {
          const active =
            selected === option;
          return (
            <Pressable
              key={option}
              onPress={() =>
                onSelect(option)
              }
              style={[
                styles.segmentButton,
                {
                  backgroundColor: active
                    ? t.primary
                    : t.surface2,
                },
              ]}
            >
              <Text
                style={[
                  styles.segmentText,
                  {
                    color: active
                      ? "#FFFFFF"
                      : t.muted,
                    fontWeight: active
                      ? "600"
                      : "500",
                  },
                ]}
              >
                {option}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}
/* -------------------------------------------------------------------------- */
/* RECURRENCE EDITOR                                                          */
/* -------------------------------------------------------------------------- */
function RecurrenceEditor({
  visible,
  task,
  onClose,
  onSave,
}: {
  visible: boolean;
  task: Task;
  onClose: () => void;
  onSave: (
    updates: Parameters<
      ReturnType<typeof useApp>["updateTask"]
    >[2],
  ) => void;
}) {
  const { t } = useApp();
  const initialKind =
    recurrenceKind(task);
  const [kind, setKind] =
    useState<RecurrenceKind>(
      initialKind,
    );
  const [selectedDays, setSelectedDays] =
    useState<string[]>(
      recurrenceDays(task),
    );
  const [customRule, setCustomRule] =
    useState(
      initialKind === "custom"
        ? task.recurrence ?? ""
        : "",
    );
  const [endMode, setEndMode] =
    useState<RecurrenceEndMode>(
      task.recurrenceEnd
        ? "date"
        : "never",
    );
  const [endDate, setEndDate] =
    useState<Date | null>(
      parseInstant(task.recurrenceEnd),
    );
  const saveRule = () => {
    if (kind === "none") {
      onSave({
        isRecurring: false,
        recurrence: null,
        recurrenceEnd: null,
      });
      return;
    }
    if (
      kind === "weekly" &&
      selectedDays.length === 0
    ) {
      Alert.alert(
        "Select a day",
        "Choose at least one day for a weekly repeat.",
      );
      return;
    }
    if (
      kind === "custom" &&
      !customRule.trim()
    ) {
      Alert.alert(
        "Custom repeat",
        "Describe the custom repeat rule.",
      );
      return;
    }
    let recurrence: string = kind;
    if (kind === "weekly") {
      const orderedDays =
        weekDays
          .map((day) => day.full)
          .filter((day) =>
            selectedDays.includes(day),
          );
      recurrence =
        weeklyRule(orderedDays);
    }
    if (kind === "custom") {
      recurrence =
        customRule.trim();
    }
    let recurrenceEnd:
      | string
      | null = null;
    if (endMode === "date") {
      if (
        !endDate ||
        endDate.getTime() <= Date.now()
      ) {
        Alert.alert(
          "Invalid end date",
          "Choose a future end date.",
        );
        return;
      }
      recurrenceEnd =
        combineLocalDateTime(
          endDate,
        ).toISOString();
    }
    onSave({
      isRecurring: true,
      recurrence,
      recurrenceEnd,
    });
  };
  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
    >
      <View style={styles.modalOverlay}>
        <Pressable
          style={StyleSheet.absoluteFill}
          onPress={onClose}
        />
        <View
          style={[
            styles.recurrenceSheet,
            {
              backgroundColor: t.bg,
            },
          ]}
        >
          <View
            style={styles.sheetHeader}
          >
            <View style={styles.sheetTitleArea}>
              <Text
                style={[
                  styles.sheetTitle,
                  {
                    color: t.text,
                    fontFamily:
                      "DMSerifDisplay",
                  },
                ]}
              >
                Repeat task
              </Text>
              <Text
                style={[
                  styles.sheetSubtitle,
                  {
                    color: t.muted,
                  },
                ]}
              >
                Choose how often this task
                comes back.
              </Text>
            </View>
            <Pressable
              onPress={onClose}
              style={[
                styles.closeButton,
                {
                  backgroundColor:
                    t.surface2,
                },
              ]}
            >
              <X
                size={15}
                color={t.muted}
              />
            </Pressable>
          </View>
          <ScrollView
            showsVerticalScrollIndicator={false}
            contentContainerStyle={
              styles.sheetContent
            }
          >
            {(
              [
                [
                  "none",
                  "Does not repeat",
                ],
                ["daily", "Daily"],
                ["weekly", "Weekly"],
                ["monthly", "Monthly"],
                ["custom", "Custom"],
              ] as const
            ).map(([value, label]) => {
              const selected =
                kind === value;
              return (
                <Pressable
                  key={value}
                  onPress={() =>
                    setKind(value)
                  }
                  style={[
                    styles.repeatOption,
                    {
                      backgroundColor:
                        selected
                          ? t.dueBg
                          : t.surface,
                      borderColor:
                        selected
                          ? t.primary
                          : t.border,
                    },
                  ]}
                >
                  <Text
                    style={[
                      styles.repeatOptionText,
                      {
                        color: selected
                          ? t.primary
                          : t.text,
                        fontWeight: selected
                          ? "600"
                          : "500",
                      },
                    ]}
                  >
                    {label}
                  </Text>
                  <View
                    style={[
                      styles.radio,
                      {
                        backgroundColor:
                          selected
                            ? t.primary
                            : t.border,
                      },
                    ]}
                  />
                </Pressable>
              );
            })}
            {/* WEEKLY */}
            {kind === "weekly" && (
              <View style={styles.subSection}>
                <Text
                  style={[
                    styles.smallLabel,
                    {
                      color: t.muted,
                    },
                  ]}
                >
                  REPEAT ON
                </Text>
                <View
                  style={styles.weekRow}
                >
                  {weekDays.map(
                    (day) => {
                      const selected =
                        selectedDays.includes(
                          day.full,
                        );
                      return (
                        <Pressable
                          key={day.full}
                          onPress={() =>
                            setSelectedDays(
                              (current) =>
                                selected
                                  ? current.filter(
                                      (
                                        value,
                                      ) =>
                                        value !==
                                        day.full,
                                    )
                                  : [
                                      ...current,
                                      day.full,
                                    ],
                            )
                          }
                          style={[
                            styles.dayButton,
                            {
                              backgroundColor:
                                selected
                                  ? t.primary
                                  : t.surface,
                              borderColor:
                                selected
                                  ? t.primary
                                  : t.border,
                            },
                          ]}
                        >
                          <Text
                            style={[
                              styles.dayText,
                              {
                                color:
                                  selected
                                    ? "#FFFFFF"
                                    : t.muted,
                              },
                            ]}
                          >
                            {day.short}
                          </Text>
                        </Pressable>
                      );
                    },
                  )}
                </View>
              </View>
            )}
            {/* CUSTOM */}
            {kind === "custom" && (
              <View style={styles.subSection}>
                <Text
                  style={[
                    styles.smallLabel,
                    {
                      color: t.muted,
                    },
                  ]}
                >
                  CUSTOM RULE
                </Text>
                <TextInput
                  value={customRule}
                  onChangeText={setCustomRule}
                  placeholder="e.g. Every 2 weeks"
                  placeholderTextColor={
                    t.muted
                  }
                  style={[
                    styles.customInput,
                    {
                      backgroundColor:
                        t.surface,
                      borderColor:
                        t.border,
                      color: t.text,
                    },
                  ]}
                />
              </View>
            )}
            {/* END */}
            {kind !== "none" && (
              <View style={styles.subSection}>
                <Text
                  style={[
                    styles.smallLabel,
                    {
                      color: t.muted,
                    },
                  ]}
                >
                  END
                </Text>
                <View
                  style={styles.endRow}
                >
                  <Pressable
                    onPress={() =>
                      setEndMode("never")
                    }
                    style={[
                      styles.endButton,
                      {
                        backgroundColor:
                          endMode ===
                          "never"
                            ? t.primary
                            : t.surface,
                        borderColor:
                          endMode ===
                          "never"
                            ? t.primary
                            : t.border,
                      },
                    ]}
                  >
                    <Text
                      style={[
                        styles.endText,
                        {
                          color:
                            endMode ===
                            "never"
                              ? "#FFFFFF"
                              : t.muted,
                        },
                      ]}
                    >
                      Never
                    </Text>
                  </Pressable>
                  <Pressable
                    onPress={() =>
                      setEndMode("date")
                    }
                    style={[
                      styles.endButton,
                      {
                        backgroundColor:
                          endMode ===
                          "date"
                            ? t.primary
                            : t.surface,
                        borderColor:
                          endMode ===
                          "date"
                            ? t.primary
                            : t.border,
                      },
                    ]}
                  >
                    <Text
                      style={[
                        styles.endText,
                        {
                          color:
                            endMode ===
                            "date"
                              ? "#FFFFFF"
                              : t.muted,
                        },
                      ]}
                    >
                      On a date
                    </Text>
                  </Pressable>
                </View>
                {endMode === "date" && (
                  <Pressable
                    onPress={() => {
                      // Simple native date picker
                      // can be added here with the
                      // same DateTimePicker pattern.
                    }}
                    style={[
                      styles.endDateButton,
                      {
                        backgroundColor:
                          t.surface,
                        borderColor:
                          t.border,
                      },
                    ]}
                  >
                    <Text
                      style={[
                        styles.valueText,
                        {
                          color: endDate
                            ? t.text
                            : t.muted,
                        },
                      ]}
                    >
                      {endDate
                        ? endDate.toLocaleDateString(
                            "en-US",
                            {
                              weekday:
                                "short",
                              month:
                                "short",
                              day: "numeric",
                            },
                          )
                        : "Select end date"}
                    </Text>
                  </Pressable>
                )}
              </View>
            )}
            {/* BUTTONS */}
            <View
              style={styles.sheetActions}
            >
              <Pressable
                onPress={onClose}
                style={[
                  styles.cancelButton,
                  {
                    backgroundColor:
                      t.surface,
                    borderColor:
                      t.border,
                  },
                ]}
              >
                <Text
                  style={[
                    styles.actionText,
                    {
                      color: t.muted,
                    },
                  ]}
                >
                  Cancel
                </Text>
              </Pressable>
              <Pressable
                onPress={saveRule}
                style={[
                  styles.saveButton,
                  {
                    backgroundColor:
                      t.primary,
                  },
                ]}
              >
                <Text
                  style={[
                    styles.actionText,
                    {
                      color: "#FFFFFF",
                    },
                  ]}
                >
                  Save repeat
                </Text>
              </Pressable>
            </View>
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}
const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 12,
  },
  backButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    alignSelf: "flex-start",
    marginBottom: 12,
  },
  backText: {
    fontSize: 14,
    textTransform: "capitalize",
  },
  titleButton: {
    width: "100%",
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 8,
  },
  title: {
    flex: 1,
    fontSize: 20,
    fontWeight: "700",
    lineHeight: 26,
  },
  titleEditRow: {
    width: "100%",
  },
  titleInput: {
    width: "100%",
    borderWidth: 1.5,
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 9,
    fontSize: 18,
    fontWeight: "600",
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingBottom: 20,
  },
  infoCard: {
    marginBottom: 12,
    borderWidth: 1,
    borderRadius: 16,
    padding: 16,
  },
  cardHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginBottom: 12,
  },
  cardTitle: {
    fontSize: 13,
    fontWeight: "700",
  },
  timingSummary: {
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 9,
    marginBottom: 10,
  },
  timingSummaryText: {
    fontSize: 12,
    fontWeight: "500",
  },
  editRow: {
    minHeight: 38,
    borderRadius: 9,
    paddingHorizontal: 12,
    marginTop: 8,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
  },
  editLabel: {
    fontSize: 11.5,
  },
  valueRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  valueText: {
    fontSize: 12,
  },
  clearText: {
    fontSize: 10,
  },
  smallLabel: {
    fontSize: 10.5,
    marginBottom: 7,
    letterSpacing: 0.3,
  },
  segmentRow: {
    flexDirection: "row",
    gap: 6,
  },
  segmentButton: {
    flex: 1,
    borderRadius: 9,
    paddingVertical: 9,
    alignItems: "center",
  },
  segmentText: {
    fontSize: 10.5,
    textTransform: "capitalize",
  },
  recurrenceHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 8,
  },
  editButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    borderRadius: 999,
    paddingHorizontal: 8,
    paddingVertical: 5,
  },
  editButtonText: {
    fontSize: 10.5,
    fontWeight: "600",
  },
  repeatRow: {
    flexDirection: "row",
    alignItems: "center",
    flexWrap: "wrap",
    gap: 8,
  },
  repeatText: {
    fontSize: 13,
  },
  repeatEnd: {
    fontSize: 11,
  },
  notesHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 8,
  },
  notesText: {
    fontSize: 12.5,
    lineHeight: 19,
  },
  notesInput: {
    minHeight: 100,
    borderWidth: 1,
    borderRadius: 12,
    padding: 12,
    fontSize: 12.5,
    lineHeight: 19,
  },
  footer: {
    paddingHorizontal: 20,
    paddingVertical: 16,
    borderTopWidth: 1,
  },
  askAIButton: {
  width: "100%",
  minHeight: 46,
  borderRadius: 12,
  borderWidth: 1,
  flexDirection: "row",
  alignItems: "center",
  justifyContent: "center",
  gap: 8,
  marginBottom: 10,
},

askAIText: {
  fontSize: 13.5,
  fontWeight: "600",
},
  completeButton: {
    width: "100%",
    minHeight: 54,
    borderRadius: 12,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  },
  completeText: {
    color: "#FFFFFF",
    fontSize: 15,
    fontWeight: "700",
  },
  completePressed: {
    opacity: 0.85,
    transform: [{ scale: 0.98 }],
  },
  pickerOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.48)",
    justifyContent: "center",
    paddingHorizontal: 20,
  },
  pickerSheet: {
    borderWidth: 1,
    borderRadius: 20,
    paddingTop: 20,
    paddingHorizontal: 16,
    paddingBottom: 16,
    overflow: "hidden",
  },
  pickerTitle: {
    fontSize: 17,
    fontWeight: "700",
    textAlign: "center",
    marginBottom: 8,
  },
  pickerActions: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: 10,
    marginTop: 10,
  },
  pickerAction: {
    minWidth: 88,
    minHeight: 42,
    borderWidth: 1,
    borderRadius: 11,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 14,
  },
  pickerCancelText: {
    fontSize: 14,
    fontWeight: "600",
  },
  pickerConfirmText: {
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "700",
  },
  /* Recurrence modal */
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.42)",
    justifyContent: "flex-end",
  },
  recurrenceSheet: {
    maxHeight: "88%",
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    paddingTop: 20,
    paddingHorizontal: 20,
  },
  sheetHeader: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    marginBottom: 16,
  },
  sheetTitleArea: {
    flex: 1,
    paddingRight: 16,
  },
  sheetTitle: {
    fontSize: 20,
    lineHeight: 25,
  },
  sheetSubtitle: {
    fontSize: 11.5,
    marginTop: 2,
  },
  closeButton: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
  },
  sheetContent: {
    paddingBottom: 24,
  },
  repeatOption: {
    minHeight: 48,
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 14,
    marginBottom: 8,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  repeatOptionText: {
    fontSize: 13,
  },
  radio: {
    width: 9,
    height: 9,
    borderRadius: 5,
  },
  subSection: {
    marginTop: 8,
  },
  weekRow: {
    flexDirection: "row",
    gap: 5,
  },
  dayButton: {
    flex: 1,
    minHeight: 38,
    borderWidth: 1,
    borderRadius: 9,
    alignItems: "center",
    justifyContent: "center",
  },
  dayText: {
    fontSize: 9.5,
    fontWeight: "600",
  },
  customInput: {
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 11,
    fontSize: 12.5,
  },
  endRow: {
    flexDirection: "row",
    gap: 8,
  },
  endButton: {
    flex: 1,
    borderWidth: 1,
    borderRadius: 12,
    paddingVertical: 11,
    alignItems: "center",
  },
  endText: {
    fontSize: 11.5,
    fontWeight: "600",
  },
  endDateButton: {
    marginTop: 8,
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 11,
  },
  sheetActions: {
    flexDirection: "row",
    gap: 8,
    marginTop: 20,
  },
  cancelButton: {
    flex: 1,
    borderWidth: 1,
    borderRadius: 12,
    paddingVertical: 13,
    alignItems: "center",
  },
  saveButton: {
    flex: 1,
    borderRadius: 12,
    paddingVertical: 13,
    alignItems: "center",
  },
  actionText: {
    fontSize: 12.5,
    fontWeight: "700",
  },
  pressed: {
    opacity: 0.6,
  },
});
