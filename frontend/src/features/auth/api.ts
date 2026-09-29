import { api } from "@/lib/api"
import type { AuthStatus, Credentials, User } from "./types"

export const authApi = {
  status: () => api.get<AuthStatus>("/api/auth/status"),
  register: (credentials: Credentials) => api.post<User>("/api/auth/register", credentials),
  login: (credentials: Credentials) => api.post<User>("/api/auth/login", credentials),
  logout: () => api.post<undefined>("/api/auth/logout"),
}
