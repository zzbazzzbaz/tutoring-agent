export interface UserOut {
  id: string
  username: string
  role: 'student' | 'teacher'
  name: string
  created_at: string
}

export interface LoginResponse {
  token: string
  user: {
    id: string
    username: string
    role: 'student' | 'teacher'
    name: string
  }
}
