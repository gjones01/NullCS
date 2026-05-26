import { APP_CONFIG } from "./config";

let runtimeApiBaseUrl =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim() || APP_CONFIG.apiBasePath;
let runtimeApiAccessToken = "";

export function getApiBaseUrl(): string {
  return runtimeApiBaseUrl;
}

export function setApiBaseUrl(next: string | null | undefined) {
  const value = String(next || "").trim();
  if (!value) return;
  runtimeApiBaseUrl = value;
}

export function getApiAccessToken(): string {
  return runtimeApiAccessToken;
}

export function setApiAccessToken(next: string | null | undefined) {
  runtimeApiAccessToken = String(next || "").trim();
}
