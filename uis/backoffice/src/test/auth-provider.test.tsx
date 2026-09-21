import { render, screen, waitFor } from '@testing-library/react';
import { renderToString } from 'react-dom/server';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthProvider, useAuth } from '@/lib/auth/context';
import { authApi } from '@/lib/auth/api';

vi.mock('@/lib/auth/api', () => ({
  authApi: {
    getMe: vi.fn(),
    isAuthenticated: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
    register: vi.fn(),
    setToken: vi.fn(),
  },
}));

function AuthStatus() {
  const { loading, user } = useAuth();

  if (loading) return <span>loading</span>;
  return <span>{user ? 'authenticated' : 'anonymous'}</span>;
}

describe('AuthProvider hydration state', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the same deterministic loading state on the server', () => {
    const html = renderToString(
      <AuthProvider>
        <AuthStatus />
      </AuthProvider>,
    );

    expect(html).toContain('loading');
    expect(authApi.isAuthenticated).not.toHaveBeenCalled();
  });

  it('resolves an anonymous session after mounting', async () => {
    vi.mocked(authApi.isAuthenticated).mockReturnValue(false);

    render(
      <AuthProvider>
        <AuthStatus />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText('anonymous')).toBeInTheDocument();
    });
    expect(authApi.getMe).not.toHaveBeenCalled();
  });

  it('loads the authenticated user after mounting', async () => {
    vi.mocked(authApi.isAuthenticated).mockReturnValue(true);
    vi.mocked(authApi.getMe).mockResolvedValue({
      id: 'user-1',
      email: 'audit@brasaland.local',
      role: 'admin',
      is_active: true,
      profile: null,
    });

    render(
      <AuthProvider>
        <AuthStatus />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText('authenticated')).toBeInTheDocument();
    });
    expect(authApi.getMe).toHaveBeenCalledOnce();
  });
});
