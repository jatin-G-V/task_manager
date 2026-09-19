import React, { useMemo, useState } from 'react'
import {
  View,
  Text,
  Pressable,
  TextInput,
  StyleSheet,
  ScrollView,
} from 'react-native'
import { useRouter } from 'expo-router'
import { SafeAreaView } from 'react-native-safe-area-context'
import { useApp } from '../context/AppContext'
import { ChevronLeft } from '../components/icons'

type FilterSection =
  | 'all'
  | 'work'
  | 'personal'
  | 'leisure'

const sectionEmoji = {
  work: '💼',
  personal: '🌿',
  leisure: '☕',
}

export default function HistoryScreen() {
  const router = useRouter()
  const { t, history } = useApp()

  const [query, setQuery] = useState('')
  const [filter, setFilter] =
    useState<FilterSection>('all')

  const filteredHistory = useMemo(() => {
    return history.filter((item) => {
      const matchesQuery = item.title
        .toLowerCase()
        .includes(query.toLowerCase())

      const matchesFilter =
        filter === 'all' ||
        item.section === filter

      return matchesQuery && matchesFilter
    })
  }, [history, query, filter])

  const groupedHistory = useMemo(() => {
    return filteredHistory.reduce<
      Record<string, typeof filteredHistory>
    >((groups, item) => {
      if (!groups[item.date]) {
        groups[item.date] = []
      }

      groups[item.date].push(item)

      return groups
    }, {})
  }, [filteredHistory])

  return (
    <SafeAreaView
      style={[
        styles.container,
        {
          backgroundColor: t.bg,
        },
      ]}
    >
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
      >
        {/* Back */}
        <Pressable
          onPress={() => router.back()}
          style={styles.backButton}
        >
          <ChevronLeft
            size={18}
            color={t.muted}
          />

          <Text
            style={[
              styles.backText,
              { color: t.muted },
            ]}
          >
            Menu
          </Text>
        </Pressable>

        {/* Header */}
        <Text
          style={[
            styles.title,
            { color: t.text },
          ]}
        >
          History
        </Text>

        <Text
          style={[
            styles.subtitle,
            { color: t.muted },
          ]}
        >
          Completed & expired tasks
        </Text>

        {/* Search */}
        <TextInput
          value={query}
          onChangeText={setQuery}
          placeholder="Search completed tasks..."
          placeholderTextColor={t.muted}
          style={[
            styles.searchInput,
            {
              color: t.text,
              borderColor: t.border,
              backgroundColor: t.bg,
            },
          ]}
        />

        {/* Filters */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.filters}
        >
          {(
            [
              ['all', 'All'],
              ['work', 'Work'],
              ['personal', 'Personal'],
              ['leisure', 'Leisure'],
            ] as [FilterSection, string][]
          ).map(([value, label]) => {
            const active = filter === value

            return (
              <Pressable
                key={value}
                onPress={() => setFilter(value)}
                style={[
                  styles.filterChip,
                  {
                    backgroundColor: active
                      ? t.text
                      : t.bg,
                    borderColor: t.border,
                  },
                ]}
              >
                <Text
                  style={[
                    styles.filterText,
                    {
                      color: active
                        ? t.bg
                        : t.muted,
                    },
                  ]}
                >
                  {label}
                </Text>
              </Pressable>
            )
          })}
        </ScrollView>

        {/* History */}
        {Object.keys(groupedHistory).length === 0 ? (
          <View style={styles.emptyState}>
            <Text
              style={[
                styles.emptyTitle,
                { color: t.text },
              ]}
            >
              No completed tasks
            </Text>

            <Text
              style={[
                styles.emptyText,
                { color: t.muted },
              ]}
            >
              Completed tasks will appear here.
            </Text>
          </View>
        ) : (
          Object.entries(groupedHistory).map(
            ([date, items]) => (
              <View
                key={date}
                style={styles.dateGroup}
              >
                <Text
                  style={[
                    styles.dateTitle,
                    { color: t.muted },
                  ]}
                >
                  {date}
                </Text>

                {items.map((item) => (
                  <View
                    key={item.id}
                    style={[
                      styles.historyCard,
                      {
                        backgroundColor: t.bg,
                        borderColor: t.border,
                      },
                    ]}
                  >
                    <View
                      style={styles.cardIcon}
                    >
                      <Text>
                        {
                          sectionEmoji[
                            item.section as
                              | 'work'
                              | 'personal'
                              | 'leisure'
                          ]
                        }
                      </Text>
                    </View>

                    <View
                      style={styles.cardContent}
                    >
                      <Text
                        style={[
                          styles.taskTitle,
                          { color: t.text },
                        ]}
                      >
                        {item.title}
                      </Text>

                      <Text
                        style={[
                          styles.taskMeta,
                          { color: t.muted },
                        ]}
                      >
                        {item.section
                          .charAt(0)
                          .toUpperCase() +
                          item.section.slice(1)}
                        {'  •  '}
                        Completed
                      </Text>
                    </View>

                    <Text style={styles.check}>
                      ✓
                    </Text>
                  </View>
                ))}
              </View>
            )
          )
        )}
      </ScrollView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },

  content: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 40,
  },

  backButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 20,
  },

  backText: {
    fontSize: 14,
    fontFamily: 'Outfit',
  },

  title: {
    fontSize: 22,
    fontWeight: '700',
    fontFamily: 'DM Serif Display',
  },

  subtitle: {
    fontSize: 13,
    marginTop: 2,
    fontFamily: 'Outfit',
  },

  searchInput: {
    height: 44,
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 14,
    marginTop: 20,
    fontSize: 14,
    fontFamily: 'Outfit',
  },

  filters: {
    gap: 8,
    paddingVertical: 14,
  },

  filterChip: {
    borderWidth: 1,
    borderRadius: 20,
    paddingHorizontal: 15,
    paddingVertical: 8,
  },

  filterText: {
    fontSize: 13,
    fontFamily: 'Outfit',
    fontWeight: '500',
  },

  dateGroup: {
    marginTop: 10,
  },

  dateTitle: {
    fontSize: 13,
    fontFamily: 'Outfit',
    fontWeight: '600',
    marginBottom: 8,
  },

  historyCard: {
    minHeight: 68,
    borderWidth: 1,
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 12,
    marginBottom: 8,
    flexDirection: 'row',
    alignItems: 'center',
  },

  cardIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 10,
  },

  cardContent: {
    flex: 1,
  },

  taskTitle: {
    fontSize: 14,
    fontWeight: '600',
    fontFamily: 'Outfit',
  },

  taskMeta: {
    fontSize: 12,
    marginTop: 3,
    fontFamily: 'Outfit',
  },

  check: {
    fontSize: 20,
    marginLeft: 10,
  },

  emptyState: {
    alignItems: 'center',
    paddingTop: 60,
  },

  emptyTitle: {
    fontSize: 16,
    fontWeight: '600',
    fontFamily: 'Outfit',
  },

  emptyText: {
    fontSize: 13,
    marginTop: 5,
    fontFamily: 'Outfit',
  },
})