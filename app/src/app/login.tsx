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

export default function LoginScreen() {
  const router = useRouter()
  const { t } = useApp()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleLogin() {
    if (!email || !password) return

    setLoading(true)

    const { error } =
      await supabase.auth.signInWithPassword({
        email,
        password,
      })

    setLoading(false)

    console.log('Login error:', error)

    if (error) {
      showAlert('Login failed', error.message)
    } else {
      router.replace('/')
    }
  }

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
            Welcome back
          </Text>

          <Text
            style={[
              styles.subtitle,
              {
                color: t.muted,
              },
            ]}
          >
            Sign in to your workspace
          </Text>
        </View>

        {/* Form */}
        <View style={styles.form}>
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
              placeholder="jatin@gmail.com"
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

          {/* Login button */}
          <TouchableOpacity
            onPress={handleLogin}
            disabled={
              loading ||
              !email ||
              !password
            }
            activeOpacity={0.8}
            style={[
              styles.loginButton,
              {
                backgroundColor:
                  email && password
                    ? t.primary
                    : t.border,
              },
            ]}
          >
            <Text
              style={[
                styles.loginButtonText,
                {
                  color:
                    email && password
                      ? '#FFFFFF'
                      : t.muted,
                },
              ]}
            >
              {loading
                ? 'Logging in...'
                : 'Log in'}
            </Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Sign up */}
      <View style={styles.signupRow}>
        <Text
          style={[
            styles.signupText,
            {
              color: t.muted,
            },
          ]}
        >
          Don't have an account?{' '}
        </Text>

        <TouchableOpacity
          onPress={() => router.push('/signup')}
          activeOpacity={0.7}
        >
          <Text
            style={[
              styles.signupLink,
              {
                color: t.primary,
              },
            ]}
          >
            Sign up
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
    marginBottom: 40,
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
    gap: 16,
  },

  label: {
    fontSize: 13,
    fontWeight: '500',
    marginBottom: 6,
  },

  input: {
    width: '100%',
    height: 52,
    borderWidth: 1.5,
    borderRadius: 12,
    paddingHorizontal: 16,
    fontSize: 15,
  },

  loginButton: {
    width: '100%',
    height: 56,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 8,
  },

  loginButtonText: {
    fontSize: 16,
    fontWeight: '600',
  },

  signupRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
  },

  signupText: {
    fontSize: 14,
  },

  signupLink: {
    fontSize: 14,
    fontWeight: '600',
  },
})

