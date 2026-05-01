import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, clearSession, getStoredSession, saveSession } from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const session = getStoredSession();
    if (!session) {
      setLoading(false);
      return;
    }
    setToken(session.token);
    if (session.user) setUser(session.user);
    api
      .me()
      .then((profile) => {
        setUser(profile);
        saveSession(session.token, profile);
      })
      .catch(() => {
        clearSession();
        setToken(null);
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const establish = useCallback(async (authResponse) => {
    saveSession(authResponse.access_token, authResponse.user);
    setToken(authResponse.access_token);
    setUser(authResponse.user);
  }, []);

  const login = useCallback(async (email, password) => {
    const res = await api.login(email, password);
    await establish(res);
  }, [establish]);

  const signup = useCallback(async (full_name, email, password) => {
    const res = await api.signup(full_name, email, password);
    await establish(res);
  }, [establish]);

  const guestLogin = useCallback(async () => {
    const res = await api.guest();
    await establish(res);
  }, [establish]);

  const logout = useCallback(async () => {
    await api.logout();
    clearSession();
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, token, loading, login, signup, guestLogin, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
