import { View, TouchableOpacity, Text, Alert } from 'react-native'
import { supabase } from '../lib/supabase'

export function LogoutButton() {
  async function handleLogout() {
    const { error } = await supabase.auth.signOut()
    if (error) {
      Alert.alert('Logout failed', error.message)
    }
    
  }

  return (
    <TouchableOpacity
      onPress={handleLogout}
      style={{ padding: 14, borderRadius: 8, backgroundColor: '#FEE2E2', alignItems: 'center' }}
    >
      <Text style={{ color: '#DC2626', fontWeight: '600' }}>Log out</Text>
    </TouchableOpacity>
  )
}