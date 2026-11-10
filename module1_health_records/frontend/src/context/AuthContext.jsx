import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { api, setSignedIn, setUnauthorizedHandler } from '../api/client.js';

const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

export const homeFor = (role) => ({ patient: '/patient', doctor: '/doctor', admin: '/admin' }[role] || '/');

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [booting, setBooting] = useState(true);

  // clearSession only wipes this browser; logout also ends the session on the server
  const clearSession = useCallback(() => {
    setSignedIn(false);
    setUser(null);
    api('/auth/session/clear', { method: 'POST', quiet: true }).catch(() => {});   // removes the cookie
  }, []);
  const logout = useCallback(async () => {
    try { await api('/auth/logout', { method: 'POST' }); } catch { /* already ended */ }
    clearSession();
  }, [clearSession]);

  useEffect(() => {
    setUnauthorizedHandler(clearSession);
    // is there a valid login cookie from earlier? (a 401 here just means "not logged in")
    api('/auth/me', { quiet: true })
      .then((r) => { setSignedIn(true); setUser(r.user); })
      .catch(() => {})
      .finally(() => setBooting(false));
  }, [clearSession]);

  async function finish(result) {
    setSignedIn(true);
    setUser(result.user);
    return result.user;
  }

  // returns the user, or { mfa: true, ticket } when a second step (authenticator code) is needed
  const login = (portal, email, password) =>
    api('/auth/login', { method: 'POST', body: { portal, email, password } })
      .then((r) => (r.mfa_required ? { mfa: true, ticket: r.ticket } : finish(r)));
  const loginSecondStep = (ticket, code) =>
    api('/auth/login/2fa', { method: 'POST', body: { ticket, code } }).then(finish);
  const refreshUser = () => api('/auth/me').then((r) => { setUser(r.user); return r.user; });
  const register = (data) => api('/auth/register', { method: 'POST', body: data }).then(finish);
  const changePassword = (current_password, new_password) =>
    api('/auth/change-password', { method: 'POST', body: { current_password, new_password } }).then(finish);

  return (
    <AuthContext.Provider value={{ user, booting, login, loginSecondStep, refreshUser, register, logout, changePassword }}>
      {children}
    </AuthContext.Provider>
  );
}
