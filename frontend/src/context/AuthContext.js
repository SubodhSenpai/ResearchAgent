'use client';

import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { getMe, login as apiLogin, register as apiRegister, logout as apiLogout, getToken, clearToken } from '@/lib/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Attempt to restore session on mount
  useEffect(() => {
    const token = getToken();
    if (token) {
      getMe()
        .then(setUser)
        .catch(() => {
          clearToken();
          setUser(null);
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const [authMessage, setAuthMessage] = useState(null);

  // Listen for forced logout (401 from API)
  useEffect(() => {
    const handler = (e) => {
      setUser(null);
      if (e.detail?.message) {
        setAuthMessage(e.detail.message);
      } else {
        setAuthMessage('Session expired. Please log in again.');
      }
    };
    window.addEventListener('auth:logout', handler);
    return () => window.removeEventListener('auth:logout', handler);
  }, []);

  const login = useCallback(async (username, password) => {
    setAuthMessage(null); // Clear any expiration messages on new login attempt
    await apiLogin(username, password);
    const me = await getMe();
    setUser(me);
    return me;
  }, []);

  const register = useCallback(async (username, email, password) => {
    setAuthMessage(null);
    const newUser = await apiRegister(username, email, password);
    return newUser;
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } finally {
      setUser(null);
      setAuthMessage(null);
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, isAuthenticated: !!user, authMessage, setAuthMessage }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
