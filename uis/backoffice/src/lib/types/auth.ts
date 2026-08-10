/**
 * Auth types for Brasaland monorepo
 */

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
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
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  profile: ProfileOut | null;
}

export interface ProfileUpdate {
  name?: string;
  phone?: string;
  address?: string;
}

export interface ForgotPasswordRequest {
  email: string;
}

export interface ResetPasswordRequest {
  token: string;
  new_password: string;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface MessageResponse {
  detail: string;
}
