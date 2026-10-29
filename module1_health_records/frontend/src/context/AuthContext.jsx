import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { api, hasToken, setToken, setUnauthorizedHandler } from '../api/client.js';

const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

export const homeFor = (role) => ({ patient: '/patient', doctor: '/doctor', admin: '/admin' }[role] || '/');

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [booting, setBooting] = useState(hasToken());

  const logout = useCallback(() => { setToken(null); setUser(null); }, []);

  useEffect(() => {
    setUnauthorizedHandler(logout);
    if (!hasToken()) return;
    api('/auth/me').then((r) => setUser(r.user)).catch(logout).finally(() => setBooting(false));
  }, [logout]);

  async function finish(result) {
    setToken(result.access_token);
    setUser(result.user);
    return result.user;
  }

  const login = (portal, email, password) =>
    api('/auth/login', { method: 'POST', body: { portal, email, password } }).then(finish);
  const register = (data) => api('/auth/register', { method: 'POST', body: data }).then(finish);

  return (
    <AuthContext.Provider value={{ user, booting, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
