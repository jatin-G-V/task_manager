import { useState } from 'react'
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  Alert,
  Platform,
  StyleSheet,
} from 'react-native'
import { useRouter } from 'expo-router'

import { supabase } from '../lib/supabase'
import { useApp } from '../context/AppContext'
import { Sparkles } from '../components/icons'

function showAlert(title: string, message: string) {
  if (Platform.OS === 'web') {
    window.alert(`${title}: ${message}`)
  } else {
    Alert.alert(title, message)
  }
}

export default function SignupScreen() {
  const router = useRouter()
  const { t } = useApp()

  const [name, setName] = useState('')
  const [profession, setProfession] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSignup() {
    setLoading(true)

    const { data, error } =
      await supabase.auth.signUp({
        email,
        password,
      })

    if (error) {
      setLoading(false)
      showAlert('Signup failed', error.message)
      return
    }

    if (data.user) {
      const { error: profileError } =
        await supabase.from('user_profile').insert({
          user_id: data.user.id,
          name,
          profession,
        })

      if (profileError) {
        console.log(
          'Profile insert error:',
          profileError
        )

        showAlert(
          'Profile save failed',
          profileError.message
        )
      }
    }

    setLoading(false)
    router.replace('/')
  }

  const isFormValid =
    name &&
    profession &&
    email &&
    password

  return (
    <View
      style={[
        styles.container,
        {
          backgroundColor: t.bg,
        },
      ]}
    >
      {/* Main content */}
      <View style={styles.mainContent}>
        {/* Logo + Heading */}
        <View style={styles.header}>
          <View style={styles.logoRow}>
            <View
              style={[
                styles.logoBox,
                {
                  backgroundColor: t.primary,
                },
              ]}
            >
              <Sparkles
                size={22}
                color="#FFFFFF"
                strokeWidth={2.5}
              />
            </View>

            <Text
              style={[
                styles.logoText,
                {
                  color: t.text,
                },
              ]}
            >
              Focal
            </Text>
          </View>

          <Text
            style={[
              styles.heading,
              {
                color: t.text,
              },
            ]}
          >
            Create your account
          </Text>

          <Text
            style={[
              styles.subtitle,
              {
                color: t.muted,
              },
            ]}
          >
            Set up your workspace in a few steps
          </Text>
        </View>

        {/* Form */}
        <View style={styles.form}>
          {/* Name */}
          <View>
            <Text
              style={[
                styles.label,
                {
                  color: t.muted,
                },
              ]}
            >
              Name
            </Text>

            <TextInput
              value={name}
              onChangeText={setName}
              placeholder="Jatin Garg"
              placeholderTextColor={t.muted}
              autoCapitalize="words"
              style={[
                styles.input,
                {
                  backgroundColor: t.surface,
                  borderColor: t.border,
                  color: t.text,
                },
              ]}
            />
          </View>

          {/* Profession */}
          <View>
            <Text
              style={[
                styles.label,
                {
                  color: t.muted,
                },
              ]}
            >
              Profession
            </Text>

            <TextInput
              value={profession}
              onChangeText={setProfession}
              placeholder="Software Engineer"
              placeholderTextColor={t.muted}
              autoCapitalize="words"
              style={[
                styles.input,
                {
                  backgroundColor: t.surface,
                  borderColor: t.border,
                  color: t.text,
                },
              ]}
            />
          </View>

          {/* Email */}
          <View>
            <Text
              style={[
                styles.label,
                {
                  color: t.muted,
                },
              ]}
            >
              Email
            </Text>

            <TextInput
              value={email}
              onChangeText={setEmail}
              placeholder="jain@gmail.com"
              placeholderTextColor={t.muted}
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="email-address"
              style={[
                styles.input,
                {
                  backgroundColor: t.surface,
                  borderColor: t.border,
                  color: t.text,
                },
              ]}
            />
          </View>

          {/* Password */}
          <View>
            <Text
              style={[
                styles.label,
                {
                  color: t.muted,
                },
              ]}
            >
              Password
            </Text>

            <TextInput
              value={password}
              onChangeText={setPassword}
              placeholder="••••••••"
              placeholderTextColor={t.muted}
              secureTextEntry
              autoCapitalize="none"
              autoCorrect={false}
              style={[
                styles.input,
                {
                  backgroundColor: t.surface,
                  borderColor: t.border,
                  color: t.text,
                },
              ]}
            />
          </View>

          {/* Sign up button */}
          <TouchableOpacity
            onPress={handleSignup}
            disabled={
              loading || !isFormValid
            }
            activeOpacity={0.8}
            style={[
              styles.signupButton,
              {
                backgroundColor:
                  isFormValid
                    ? t.primary
                    : t.border,
              },
            ]}
          >
            <Text
              style={[
                styles.signupButtonText,
                {
                  color:
                    isFormValid
                      ? '#FFFFFF'
                      : t.muted,
                },
              ]}
            >
              {loading
                ? 'Creating account...'
                : 'Sign up'}
            </Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Login */}
      <View style={styles.loginRow}>
        <Text
          style={[
            styles.loginText,
            {
              color: t.muted,
            },
          ]}
        >
          Already have an account?{' '}
        </Text>

        <TouchableOpacity
          onPress={() => router.push('/login')}
          activeOpacity={0.7}
        >
          <Text
            style={[
              styles.loginLink,
              {
                color: t.primary,
              },
            ]}
          >
            Log in
          </Text>
        </TouchableOpacity>
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    paddingHorizontal: 32,
    paddingTop: 48,
    paddingBottom: 40,
  },

  mainContent: {
    flex: 1,
    justifyContent: 'center',
  },

  header: {
    marginBottom: 32,
  },

  logoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 12,
  },

  logoBox: {
    width: 42,
    height: 42,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },

  logoText: {
    fontSize: 22,
    fontWeight: '700',
  },

  heading: {
    fontSize: 28,
    fontWeight: '700',
    lineHeight: 34,
  },

  subtitle: {
    fontSize: 15,
    marginTop: 6,
  },

  form: {
    gap: 14,
  },

  label: {
    fontSize: 13,
    fontWeight: '500',
    marginBottom: 6,
  },

  input: {
    width: '100%',
    height: 50,
    borderWidth: 1.5,
    borderRadius: 12,
    paddingHorizontal: 16,
    fontSize: 15,
  },

  signupButton: {
    width: '100%',
    height: 56,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 6,
  },

  signupButtonText: {
    fontSize: 16,
    fontWeight: '600',
  },

  loginRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
  },

  loginText: {
    fontSize: 14,
  },

  loginLink: {
    fontSize: 14,
    fontWeight: '600',
  },
})
