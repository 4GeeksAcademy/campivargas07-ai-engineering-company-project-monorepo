/**
 * Auth types for Brasaland monorepo
 */

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type?: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  role?: string;
  name?: string;
  phone?: string;
  address?: string;
}

export interface UserOut {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
}

export interface ProfileOut {
  id: string;
  user_id: string;
  name: string;
  phone: string;
  address: string;
}

export interface AuthMeResponse {
  user: UserOut & {
    uuid?: string | null;
    created_at: string;
  };
  profile: ProfileOut | null;
}

export interface ProfileUpdate {
  name?: string;
  phone?: string;
  address?: string;
}

