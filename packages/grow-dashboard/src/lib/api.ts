export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const opts: RequestInit = {
    method,
    headers: { 'Content-Type': 'application/json' }
  };
  if (body !== undefined) {
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  if (!res.ok) {
    throw new ApiError(res.status, `${method} ${path}: ${res.status}`);
  }
  if (res.status === 204) return null as T;
  return res.json();
}

export function get<T>(path: string): Promise<T> {
  return request<T>('GET', path);
}

export function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>('POST', path, body);
}

export function put<T>(path: string, body: unknown): Promise<T> {
  return request<T>('PUT', path, body);
}

export function del<T>(path: string): Promise<T> {
  return request<T>('DELETE', path);
}

export function patch<T>(path: string, body: unknown): Promise<T> {
  return request<T>('PATCH', path, body);
}

// -- Device Groups --

import type { DeviceGroup, GroupsResponse } from '$lib/types.js';

export function getGroups(): Promise<GroupsResponse> {
  return get<GroupsResponse>('/api/groups');
}

export function createGroup(body: {
  name: string;
  category: string;
  device_ids: string[];
  color: string;
}): Promise<DeviceGroup> {
  return post<DeviceGroup>('/api/groups', body);
}

export function updateGroup(
  id: string,
  body: { name: string; category: string; device_ids: string[]; color: string }
): Promise<DeviceGroup> {
  return put<DeviceGroup>(`/api/groups/${id}`, body);
}

export function deleteGroup(id: string): Promise<void> {
  return del<void>(`/api/groups/${id}`);
}
