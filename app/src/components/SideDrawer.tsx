import React from 'react'
import { View, Text, Pressable, StyleSheet } from 'react-native'
import { LinearGradient } from 'expo-linear-gradient'
import { useRouter } from 'expo-router'
import { SafeAreaView } from 'react-native-safe-area-context'
import { useApp } from '../context/AppContext'
import { supabase } from '../lib/supabase'
import { Archive, Bell, LogOut, X, ChevronRight } from './icons'

export default function SideDrawer() {
  const { t, user } = useApp()
  const router = useRouter()

  const items = [
    { label: 'History', icon: Archive, onTap: () => router.push('/history') },
    { label: 'Notification Settings', icon: Bell, onTap: () => {} },
  ]

  const handleLogout = async () => {
    await supabase.auth.signOut()
  }

  const userName = user?.name && user.name.trim().length > 0 ? user.name : 'User'
  const userEmail = user?.email && user.email.trim().length > 0 ? user.email : ''
  const initials = userName.split(' ').filter(Boolean).map((n) => n[0]).join('').slice(0, 2).toUpperCase()

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: t.bg }]}>
      {/* HEADER */}
      <View style={[styles.header, { borderBottomColor: t.border }]}>
        <Text style={[styles.headerTitle, { color: t.text }]}>Menu</Text>
        <Pressable onPress={() => router.back()} style={[styles.closeButton, { backgroundColor: t.surface2 }]}>
          <X size={18} color={t.muted} />
        </Pressable>
      </View>

      {/* USER CARD */}
      <View style={[styles.userCard, { backgroundColor: t.surface, borderColor: t.border }]}>
        <LinearGradient colors={[t.primary, `${t.primary}88`]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.avatar}>
          <Text style={styles.avatarText}>{initials || 'U'}</Text>
        </LinearGradient>

        <Text style={[styles.userName, { color: t.text }]}>{userName}</Text>

        {userEmail ? <Text style={[styles.userEmail, { color: t.muted }]}>{userEmail}</Text> : null}

        {user?.profession ? (
          <View style={[styles.professionBadge, { backgroundColor: t.surface2 }]}>
            <Text style={[styles.professionText, { color: t.muted }]}>{user.profession}</Text>
          </View>
        ) : null}
      </View>

      {/* MENU ITEMS */}
      <View style={styles.navContainer}>
        {items.map((item) => {
          const Icon = item.icon
          return (
            <Pressable key={item.label} onPress={item.onTap} style={[styles.navItem, { backgroundColor: t.surface, borderColor: t.border }]}>
              <View style={[styles.iconContainer, { backgroundColor: t.surface2 }]}>
                <Icon size={18} color={t.muted} />
              </View>
              <Text style={[styles.navLabel, { color: t.text }]}>{item.label}</Text>
              <ChevronRight size={16} color={t.muted} />
            </Pressable>
          )
        })}
      </View>

      {/* LOGOUT */}
      <View style={styles.logoutContainer}>
        <Pressable onPress={handleLogout} style={[styles.logoutButton, { backgroundColor: `${t.risk}14`, borderColor: `${t.risk}30` }]}>
          <View style={[styles.iconContainer, { backgroundColor: `${t.risk}20` }]}>
            <LogOut size={18} color={t.risk} />
          </View>
          <Text style={[styles.logoutText, { color: t.risk }]}>Log Out</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    width: '100%',
  },

  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingTop: 20,
    paddingBottom: 16,
    borderBottomWidth: 1,
  },

  headerTitle: {
    fontSize: 16,
    fontWeight: '600',
  },

  closeButton: {
    width: 34,
    height: 34,
    borderRadius: 17,
    alignItems: 'center',
    justifyContent: 'center',
  },

  closeText: {
    fontSize: 24,
    lineHeight: 28,
    fontWeight: '300',
  },

  userCard: {
    marginHorizontal: 16,
    marginTop: 16,
    paddingHorizontal: 20,
    paddingVertical: 20,
    borderRadius: 16,
    borderWidth: 1,
  },

  avatar: {
    width: 52,
    height: 52,
    borderRadius: 26,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
  },

  avatarText: {
    fontSize: 20,
    fontWeight: '700',
    color: '#FFFFFF',
  },

  userName: {
    fontSize: 16,
    fontWeight: '600',
  },

  userEmail: {
    fontSize: 13,
    marginTop: 2,
  },

  professionBadge: {
    alignSelf: 'flex-start',
    marginTop: 8,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
  },

  professionText: {
    fontSize: 11.5,
  },

  navContainer: {
    flex: 1,
    paddingHorizontal: 16,
    paddingTop: 16,
    gap: 8,
  },

  navItem: {
    width: '100%',
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 16,
    borderRadius: 16,
    borderWidth: 1,
  },

  iconContainer: {
    width: 36,
    height: 36,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },

  iconText: {
    fontSize: 18,
    fontWeight: '600',
  },

  navLabel: {
    flex: 1,
    marginLeft: 12,
    fontSize: 15,
    fontWeight: '500',
  },

  chevron: {
    fontSize: 24,
    lineHeight: 24,
  },

  logoutContainer: {
    paddingHorizontal: 16,
    paddingBottom: 40,
  },

  logoutButton: {
    width: '100%',
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 16,
    borderRadius: 16,
    borderWidth: 1,
  },

  logoutText: {
    marginLeft: 12,
    fontSize: 15,
    fontWeight: '500',
  },
})