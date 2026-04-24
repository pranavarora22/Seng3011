import { mockSignup, mockLogin, mockRefresh } from "./mockAuth";

const AUTH_API = import.meta.env.VITE_AUTH_API_URL || "";
const USE_MOCK = !AUTH_API;

const TOKEN_KEY = "seng3011_access_token";
const REFRESH_KEY = "seng3011_refresh_token";
const USER_KEY = "seng3011_user";

export function getAccessToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function getUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || "null");
  } catch {
    return null;
  }
}

export function isAuthenticated() {
  const token = getAccessToken();
  if (!token) return false;
  try {
    const part = token.startsWith("mock.") ? token.split(".")[1] : token.split(".")[1];
    const payload = JSON.parse(atob(part));
    return payload.exp * 1000 > Date.now();
  } catch {
    return false;
  }
}

function _saveSession(data) {
  localStorage.setItem(TOKEN_KEY, data.access_token);
  localStorage.setItem(REFRESH_KEY, data.refresh_token);
  localStorage.setItem(USER_KEY, JSON.stringify(data.user));
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(USER_KEY);
}

async function _parseResponse(res, fallback) {
  let data;
  try {
    data = await res.json();
  } catch {
    throw new Error("Could not reach the auth server. Check your VITE_AUTH_API_URL setting.");
  }
  if (!res.ok) throw new Error(data.error || fallback);
  return data;
}

export async function signup({ name, email, password }) {
  if (USE_MOCK) {
    const data = await mockSignup({ name, email, password });
    _saveSession(data);
    return data.user;
  }
  let res;
  try {
    res = await fetch(`${AUTH_API}/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, password }),
    });
  } catch {
    throw new Error("Could not reach the auth server. Check your VITE_AUTH_API_URL setting.");
  }
  const data = await _parseResponse(res, "Signup failed");
  _saveSession(data);
  return data.user;
}

export async function login({ email, password }) {
  if (USE_MOCK) {
    const data = await mockLogin({ email, password });
    _saveSession(data);
    return data.user;
  }
  let res;
  try {
    res = await fetch(`${AUTH_API}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
  } catch {
    throw new Error("Could not reach the auth server. Check your VITE_AUTH_API_URL setting.");
  }
  const data = await _parseResponse(res, "Login failed");
  _saveSession(data);
  return data.user;
}

export async function refreshAccessToken() {
  const refreshToken = localStorage.getItem(REFRESH_KEY);
  if (!refreshToken) throw new Error("No refresh token");
  if (USE_MOCK) {
    const data = await mockRefresh(refreshToken);
    localStorage.setItem(TOKEN_KEY, data.access_token);
    return data.access_token;
  }
  let res;
  try {
    res = await fetch(`${AUTH_API}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  } catch {
    throw new Error("Could not reach the auth server.");
  }
  const data = await _parseResponse(res, "Session expired");
  localStorage.setItem(TOKEN_KEY, data.access_token);
  return data.access_token;
}
