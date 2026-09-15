import { useState } from 'react'
import { View, Text, TextInput, TouchableOpacity, Alert } from 'react-native'
import { supabase } from '../lib/supabase'
import { useRouter } from 'expo-router'

export default function SignupScreen() {
  const [name, setName] = useState('')
  const [profession, setProfession] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const router = useRouter()

  async function handleSignup() {
    setLoading(true)
    const { data, error } = await supabase.auth.signUp({ email, password })

    if (error) {
      setLoading(false)
      Alert.alert('Signup failed', error.message)
      return
    }
    if (data.user) {
  const { error: profileError } = await supabase.from('user_profile').insert({
    user_id: data.user.id,
    name,
    profession,
  })

  if (profileError) {
    console.log('Profile insert error:', profileError)
    Alert.alert('Profile save failed', profileError.message)
  }
}
 

    setLoading(false)
    router.replace('/')
  }

  return (
    <View style={{ flex: 1, justifyContent: 'center', padding: 24 }}>
      <Text style={{ fontSize: 24, fontWeight: 'bold', marginBottom: 24 }}>Sign up</Text>

      <TextInput placeholder="Name" value={name} onChangeText={setName}
        style={{ borderWidth: 1, borderColor: '#ccc', borderRadius: 8, padding: 12, marginBottom: 12 }} />
      <TextInput placeholder="What do you do? (e.g. Software Engineer)" value={profession} onChangeText={setProfession}
        style={{ borderWidth: 1, borderColor: '#ccc', borderRadius: 8, padding: 12, marginBottom: 12 }} />
      <TextInput placeholder="Email" value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address"
        style={{ borderWidth: 1, borderColor: '#ccc', borderRadius: 8, padding: 12, marginBottom: 12 }} />
      <TextInput placeholder="Password" value={password} onChangeText={setPassword} secureTextEntry
        style={{ borderWidth: 1, borderColor: '#ccc', borderRadius: 8, padding: 12, marginBottom: 20 }} />

      <TouchableOpacity onPress={handleSignup} disabled={loading}
        style={{ backgroundColor: '#2563EB', padding: 14, borderRadius: 8, alignItems: 'center' }}>
        <Text style={{ color: 'white', fontWeight: '600' }}>{loading ? 'Creating account...' : 'Sign up'}</Text>
      </TouchableOpacity>
    </View>
  )
}

