import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, clearTokens, getAccessToken, saveTokens } from "./api";
import type { Me, Role } from "./types";

type AuthState = {
  me: Me | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

const writers = new Set<Role>(["admin", "hr"]);

export function canWriteEmployees(role: Role): boolean {
  return writers.has(role);
}

export function canManageDepartments(role: Role): boolean {
  return writers.has(role);
}

export function canCorrectAttendance(role: Role): boolean {
  return writers.has(role);
}

export function canApproveLeave(role: Role): boolean {
  return role === "admin" || role === "hr" || role === "manager";
}

export function canManageLeave(role: Role): boolean {
  return writers.has(role);
}

export function canReadAudit(role: Role): boolean {
  return role === "admin";
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!getAccessToken()) {
      setReady(true);
      return;
    }
    api<Me>("/auth/me")
      .then(setMe)
      .catch(() => {
        clearTokens();
        setMe(null);
      })
      .finally(() => setReady(true));
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      me,
      ready,
      async login(email, password) {
        const tokens = await api<{ access_token: string; refresh_token: string }>("/auth/login", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        });
        saveTokens(tokens.access_token, tokens.refresh_token);
        setMe(await api<Me>("/auth/me"));
      },
      async logout() {
        const refresh = sessionStorage.getItem("ems.refresh");
        try {
          if (refresh) {
            await api("/auth/logout", {
              method: "POST",
              body: JSON.stringify({ refresh_token: refresh }),
            });
          }
        } finally {
          clearTokens();
          setMe(null);
        }
      },
    }),
    [me, ready],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const value = useContext(AuthContext);
  if (!value) throw new Error("AuthProvider is missing");
  return value;
}
