import type { AuthMeResponse, LoginRequest, RegisterRequest, TokenResponse, ProfileUpdate, ProfileOut } from '../types/auth';

export class AuthApiClient {
  private token: string | null = null;

  private getBaseUrl(): string {
    if (typeof window !== 'undefined') {
      return '/api';
    }
    const raw = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    return raw.replace(/\/+$/, '');
  }

  setToken(token: string | null) {
    this.token = token;
    if (typeof window !== 'undefined') {
      if (token) {
        localStorage.setItem('brasaland_token', token);
      } else {
        localStorage.removeItem('brasaland_token');
      }
    }
  }

  getToken(): string | null {
    if (this.token) return this.token;
    if (typeof window !== 'undefined') {
      this.token = localStorage.getItem('brasaland_token');
    }
    return this.token;
  }

  private getHeaders(): HeadersInit {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };
    
    const token = this.getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    
    return headers;
  }

  private async handleResponse<T>(response: Response): Promise<T> {
    if (response.status === 401) {
      this.setToken(null);
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
      throw new Error('Unauthorized');
    }
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
      throw new Error(error.detail || 'Error en la solicitud');
    }
    
    return response.json();
  }

  async login(data: LoginRequest): Promise<TokenResponse> {
    const response = await fetch(`${this.getBaseUrl()}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    
    const result = await this.handleResponse<TokenResponse>(response);
    this.setToken(result.access_token);
    return result;
  }

  async register(data: RegisterRequest): Promise<{ id: string; email: string; role: string; is_active: boolean }> {
    const response = await fetch(`${this.getBaseUrl()}/users`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    
    return this.handleResponse(response);
  }

  async getMe(): Promise<AuthMeResponse> {
    const response = await fetch(`${this.getBaseUrl()}/auth/me`, {
      headers: this.getHeaders(),
    });
    
    return this.handleResponse<AuthMeResponse>(response);
  }

  async getProfile(): Promise<ProfileOut> {
    const response = await fetch(`${this.getBaseUrl()}/profiles/me`, {
      headers: this.getHeaders(),
    });
    
    return this.handleResponse<ProfileOut>(response);
  }

  async updateProfile(data: ProfileUpdate): Promise<ProfileOut> {
    const response = await fetch(`${this.getBaseUrl()}/profiles/me`, {
      method: 'PUT',
      headers: this.getHeaders(),
      body: JSON.stringify(data),
    });
    
    return this.handleResponse<ProfileOut>(response);
  }

  logout() {
    this.setToken(null);
    if (typeof window !== 'undefined') {
      window.location.href = '/login';
    }
  }

  isAuthenticated(): boolean {
    return this.getToken() !== null;
  }
}

export const authApi = new AuthApiClient();

