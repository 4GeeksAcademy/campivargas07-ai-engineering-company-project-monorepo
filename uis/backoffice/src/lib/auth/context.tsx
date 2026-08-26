'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import type { AuthMeResponse } from '../types/auth';
import { authApi } from './api';

interface AuthContextType {
  user: AuthMeResponse | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (data: { email: string; password: string; name?: string; phone?: string; address?: string }) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthMeResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = async () => {
    if (!authApi.isAuthenticated()) {
      setUser(null);
      setLoading(false);
      return;
    }

    try {
      const userData = await authApi.getMe();
      setUser(userData);
    } catch (error) {
      console.error('Error fetching user:', error);
      setUser(null);
      authApi.setToken(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshUser();
  }, []);

  const login = async (email: string, password: string) => {
    await authApi.login({ email, password });
    await refreshUser();
  };

  const register = async (data: { email: string; password: string; name?: string; phone?: string; address?: string; role?: string }) => {
    await authApi.register({
      ...data,
      role: data.role || 'admin',
    });
    await login(data.email, data.password);
  };

  const logout = () => {
    authApi.logout();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
