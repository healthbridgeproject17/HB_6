// All calls to the Flask API go through here. The login token is kept in
// sessionStorage (cleared when the browser tab closes) and sent on every call.
const BASE = '/api/v1';
let token = sessionStorage.getItem('hb_token');
let onUnauthorized = null;

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

export function setToken(value) {
  token = value;
  if (value) sessionStorage.setItem('hb_token', value);
  else sessionStorage.removeItem('hb_token');
}
export const hasToken = () => Boolean(token);
export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn; };

export async function api(path, { method = 'GET', body, form, raw } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload;
  if (form) {
    payload = form; // browser sets the multipart header itself
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }

  let res;
  try {
    res = await fetch(BASE + path, { method, headers, body: payload });
  } catch {
    throw new ApiError(0, 'Cannot reach the server. Is the API running?');
  }

  if (raw) {
    if (!res.ok) throw new ApiError(res.status, 'Not available');
    return res.blob();
  }

  let data = null;
  try { data = await res.json(); } catch { /* empty body */ }
  if (!res.ok) {
    if (res.status === 401 && token && onUnauthorized) onUnauthorized();
    throw new ApiError(res.status, data?.error || data?.msg || 'Request failed');
  }
  return data;
}
