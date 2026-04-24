// Local mock auth — only used when VITE_AUTH_API_URL is not set.
// Stores users in localStorage so sessions survive page refresh.

const MOCK_USERS_KEY = "mock_auth_users";

function _getUsers() {
  try { return JSON.parse(localStorage.getItem(MOCK_USERS_KEY) || "{}"); }
  catch { return {}; }
}

function _saveUsers(users) {
  localStorage.setItem(MOCK_USERS_KEY, JSON.stringify(users));
}

function _makeToken(payload, expiresInSeconds) {
  const exp = Math.floor(Date.now() / 1000) + expiresInSeconds;
  const data = btoa(JSON.stringify({ ...payload, exp, iat: Math.floor(Date.now() / 1000) }));
  // structure mimics a JWT so isAuthenticated() can decode it
  return `mock.${data}.sig`;
}

export async function mockSignup({ name, email, password }) {
  await new Promise((r) => setTimeout(r, 400)); // feel like a real request
  const users = _getUsers();
  const key = email.toLowerCase();
  if (users[key]) throw new Error("Email already registered");
  if (!email || !password) throw new Error("Email and password are required");
  const user = { id: crypto.randomUUID(), email: key, name: name || "", password };
  users[key] = user;
  _saveUsers(users);
  return {
    user: { id: user.id, email: user.email, name: user.name },
    access_token: _makeToken({ sub: user.id, email: user.email, type: "access" }, 3600),
    refresh_token: _makeToken({ sub: user.id, email: user.email, type: "refresh" }, 604800),
  };
}

export async function mockLogin({ email, password }) {
  await new Promise((r) => setTimeout(r, 400));
  const users = _getUsers();
  const key = email.toLowerCase();
  const user = users[key];
  if (!user || user.password !== password) throw new Error("Invalid email or password");
  return {
    user: { id: user.id, email: user.email, name: user.name },
    access_token: _makeToken({ sub: user.id, email: user.email, type: "access" }, 3600),
    refresh_token: _makeToken({ sub: user.id, email: user.email, type: "refresh" }, 604800),
  };
}

export async function mockRefresh(refreshToken) {
  await new Promise((r) => setTimeout(r, 200));
  try {
    const payload = JSON.parse(atob(refreshToken.split(".")[1]));
    if (payload.type !== "refresh" || payload.exp * 1000 < Date.now()) {
      throw new Error("Refresh token expired");
    }
    return {
      access_token: _makeToken({ sub: payload.sub, email: payload.email, type: "access" }, 3600),
    };
  } catch {
    throw new Error("Invalid refresh token");
  }
}
