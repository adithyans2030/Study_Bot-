import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { authApi } from "./api"
import type { AuthStatus, Credentials } from "./types"

export const authStatusKey = ["auth", "status"] as const

export function useAuthStatus() {
  return useQuery({ queryKey: authStatusKey, queryFn: authApi.status })
}

function useSignedInMutation(fn: (credentials: Credentials) => ReturnType<typeof authApi.login>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: (user) => {
      queryClient.setQueryData<AuthStatus>(authStatusKey, (previous) => ({
        has_users: true,
        registration_open: previous?.registration_open ?? false,
        user,
      }))
    },
  })
}

export function useLogin() {
  return useSignedInMutation(authApi.login)
}

export function useRegister() {
  return useSignedInMutation(authApi.register)
}

export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: authApi.logout,
    onSuccess: () => {
      queryClient.setQueryData<AuthStatus>(authStatusKey, (previous) => ({
        has_users: previous?.has_users ?? true,
        registration_open: previous?.registration_open ?? false,
        user: null,
      }))
      // Every other query may hold another account's data (a different collection list, chat
      // history, ...); drop it all rather than risk showing it to whoever signs in next.
      queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== "auth" })
    },
  })
}
