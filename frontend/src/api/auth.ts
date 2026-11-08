import { apiClient } from "./client"

export interface AuthUser {
  id: number
  name: string
  username: string
}

export interface AuthResult {
  user: AuthUser
  token: string
}

export async function login(username: string): Promise<AuthResult> {
  const res = await apiClient.post<AuthResult>("/auth/login", { username })
  return res.data
}

export async function register(username: string, name?: string): Promise<AuthResult> {
  const res = await apiClient.post<AuthResult>("/auth/register", { username, name })
  return res.data
}

export async function logout(): Promise<void> {
  await apiClient.post("/auth/logout")
}
