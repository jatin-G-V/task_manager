// lib/apiClient.ts

import { supabase } from './supabase';

export async function apiFetch(
  path: string,
  options: RequestInit = {}
) {
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    throw new Error('Not logged in');
  }

  const send = (accessToken: string) => fetch(
    `${process.env.EXPO_PUBLIC_API_URL}${path}`,
    {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${accessToken}`,
        ...options.headers,
      },
    }
  );

  let response = await send(session.access_token);

  // The app may resume with a token that expired while it was in the
  // background. Refresh once, then retry the original request once.
  if (response.status === 401) {
    const { data, error } = await supabase.auth.refreshSession();
    const refreshedToken = data.session?.access_token;
    if (!error && refreshedToken && refreshedToken !== session.access_token) {
      response = await send(refreshedToken);
    }
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));

    throw new Error(
      body.detail || `Request failed: ${response.status}`
    );
  }

  return response.json();
}
