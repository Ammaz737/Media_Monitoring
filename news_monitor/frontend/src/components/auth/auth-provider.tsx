"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { usePathname, useRouter } from "next/navigation";
import { api, getAuthToken, setAuthToken } from "@/lib/api";
import type { AuthUser } from "@/lib/types";

interface AuthContextValue {
  user: AuthUser;
  can: (perm: string) => boolean;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (!getAuthToken()) {
      setReady(true);
      return;
    }
    api
      .me()
      .then((res) => {
        if (!cancelled) setUser(res.user);
      })
      .catch(() => {
        if (!cancelled) {
          setAuthToken(null);
          setUser(null);
        }
      })
      .finally(() => {
        if (!cancelled) setReady(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      /* ignore */
    }
    setAuthToken(null);
    setUser(null);
    router.replace("/login");
  }, [router]);

  const can = useCallback(
    (perm: string) => Boolean(user?.permissions?.includes(perm)),
    [user]
  );

  const value = useMemo(
    () => (user ? { user, can, logout } : null),
    [user, can, logout]
  );

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#F8FAFC] text-sm text-slate-500">
        Loading…
      </div>
    );
  }

  if (pathname === "/login") {
    if (user) {
      router.replace("/");
      return null;
    }
    return <>{children}</>;
  }

  if (!user || !value) {
    router.replace("/login");
    return null;
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
