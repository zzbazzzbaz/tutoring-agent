"use client";

import { createContext, useContext, type ReactNode } from "react";

// Minimal stub - will be replaced in Task 3
const AuthContext = createContext<{ token: string | null }>({ token: null });

export function AuthProvider({ children }: { children: ReactNode }) {
  return (
    <AuthContext.Provider value={{ token: null }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
