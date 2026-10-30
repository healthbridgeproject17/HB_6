import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { api, hasToken, setToken, setUnauthorizedHandler } from '../api/client.js';

const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

export const homeFor = (role) => ({ patient: '/patient', doctor: '/doctor', admin: '/admin' }[role] || '/');

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [booting, setBooting] = useState(hasToken());

  // clearSession only wipes this browser; logout also ends the session on the server
  const clearSession = useCallback(() => { setToken(null); setUser(null); }, []);
  const logout = useCallback(async () => {
    try { await api('/auth/logout', { method: 'POST' }); } catch { /* already ended */ }
    clearSession();
  }, [clearSession]);

  useEffect(() => {
    setUnauthorizedHandler(clearSession);
    if (!hasToken()) return;
    api('/auth/me').then((r) => setUser(r.user)).catch(clearSession).finally(() => setBooting(false));
  }, [clearSession]);

  async function finish(result) {
    setToken(result.access_token);
    setUser(result.user);
    return result.user;
  }

  const login = (portal, email, password) =>
    api('/auth/login', { method: 'POST', body: { portal, email, password } }).then(finish);
  const register = (data) => api('/auth/register', { method: 'POST', body: data }).then(finish);
  const changePassword = (current_password, new_password) =>
    api('/auth/change-password', { method: 'POST', body: { current_password, new_password } }).then(finish);

  return (
    <AuthContext.Provider value={{ user, booting, login, register, logout, changePassword }}>
      {children}
    </AuthContext.Provider>
  );
}
