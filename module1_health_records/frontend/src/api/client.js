// All calls to the Flask API go through here. The login lives in an HttpOnly cookie that the
// browser sends by itself (JavaScript cannot read it). For changes (POST/PUT/PATCH/DELETE) we
// also send the CSRF code, which the server puts in a separate readable cookie.
const BASE = '/api/v1';
let signedIn = false;
let onUnauthorized = null;

function csrfToken() {
  const match = document.cookie.split('; ').find((c) => c.startsWith('csrf_access_token='));
  return match ? decodeURIComponent(match.split('=')[1]) : '';
}

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

export const setSignedIn = (value) => { signedIn = Boolean(value); };
export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn; };

export async function api(path, { method = 'GET', body, form, raw, quiet } = {}) {
  const headers = { 'X-Auth-Mode': 'cookie' };
  if (method !== 'GET') headers['X-CSRF-TOKEN'] = csrfToken();
  let payload;
  if (form) {
    payload = form; // browser sets the multipart header itself
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }

  let res;
  try {
    res = await fetch(BASE + path, { method, headers, body: payload, credentials: 'same-origin' });
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
    if (res.status === 401 && signedIn && !quiet && onUnauthorized) onUnauthorized();
    throw new ApiError(res.status, data?.error || data?.msg || 'Request failed');
  }
  return data;
}
