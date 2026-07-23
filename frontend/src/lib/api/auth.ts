import { api } from "./client";
import type { LoginResponse, User } from "@/lib/types";

export const authApi = {
  login: (username: string, password: string) =>
    api.post<LoginResponse>("/auth/login", { username, password }),

  logout: () => api.post<void>("/auth/logout"),

  me: () => api.get<User>("/auth/me"),

  changePassword: (oldPassword: string, newPassword: string) =>
    api.post<void>("/auth/change-password", {
      old_password: oldPassword,
      new_password: newPassword,
    }),
};
