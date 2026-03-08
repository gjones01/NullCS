export const APP_CONFIG = {
  appName: "NullCS",
  apiBasePath: "/api",
  isDev: import.meta.env.DEV,
  isProd: import.meta.env.PROD,
} as const;

export const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim() || APP_CONFIG.apiBasePath;
