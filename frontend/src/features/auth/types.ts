export interface User {
  id: number
  username: string
  is_admin: boolean
}

export interface AuthStatus {
  has_users: boolean
  registration_open: boolean
  user: User | null
}

export interface Credentials {
  username: string
  password: string
}
