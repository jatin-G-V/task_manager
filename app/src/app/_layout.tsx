import { useEffect, useState } from 'react'
import { Slot, useRouter, useSegments } from 'expo-router'
import { supabase } from '../lib/supabase'
import { AppProvider } from '../context/AppContext'

export default function RootLayout() {
  const [session, setSession] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  const router = useRouter()
  const segments = useSegments()

  useEffect(() => {
    // App open --> Existing session check
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      setLoading(false)
    })

    // Login / logout = session update 
    const { data: listener } =
      supabase.auth.onAuthStateChange((_event, session) => {
        setSession(session)
      })

    return () => {
      listener.subscription.unsubscribe()
    }
  }, [])

  useEffect(() => {
    if (loading) return

    const inAuthGroup =
      segments[0] === 'login' ||
      segments[0] === 'signup'

    // Logged out
    if (!session && !inAuthGroup) {
      router.replace('/login')
    }

    // Logged in 
    else if (session && inAuthGroup) {
      router.replace('/')
    }
  }, [session, loading, segments])

  if (loading) {
    return null
  }

  return (
    <AppProvider>
      <Slot />
    </AppProvider>
  )
}

