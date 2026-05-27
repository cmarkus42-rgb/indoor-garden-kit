import { writable, readonly } from 'svelte/store';
import { post } from './api.js';
import type { AuthResponse } from './types.js';

const STORAGE_KEY = 'grow_auth_verified';

function loadInitial(): boolean {
  if (typeof localStorage === 'undefined') return false;
  return localStorage.getItem(STORAGE_KEY) === 'true';
}

const _verified = writable(loadInitial());
export const verified = readonly(_verified);

export async function verifyPin(pin: string): Promise<boolean> {
  const res = await post<AuthResponse>('/api/auth/verify', { pin });
  if (res.verified) {
    localStorage.setItem(STORAGE_KEY, 'true');
    _verified.set(true);
  }
  return res.verified;
}

export function clearAuth() {
  localStorage.removeItem(STORAGE_KEY);
  _verified.set(false);
}
