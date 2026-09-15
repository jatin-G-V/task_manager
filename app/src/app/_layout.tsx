import { useEffect, useState } from 'react';
import { Slot, useRouter, useSegments } from 'expo-router';
import { supabase } from '../lib/supabase';
import { LogoutButton } from '../components/LogoutButton'

// apne screen ke JSX ke andar:

export default function RootLayout() {
  const [session, setSession] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const segments = useSegments();

  useEffect(() => {
    // app khulte hi current session check karo
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setLoading(false);
    });

    // login/logout hone par session update karo
    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
    });

    return () => listener.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (loading) return;

    const inAuthGroup = segments[0] === 'login' || segments[0] === 'signup';

    if (!session && !inAuthGroup) {
      router.replace('/login'); // logged in nahi hai, login pe bhejo
    } else if (session && inAuthGroup) {
      router.replace('/'); // logged in hai, dashboard pe bhejo
    }
  }, [session, loading, segments]);

  if (loading) return null; // ya ek chhota loading spinner
  return <Slot />;
}