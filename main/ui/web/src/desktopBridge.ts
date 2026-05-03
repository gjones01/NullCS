import { invoke } from "@tauri-apps/api/core";

export type DesktopServiceStatus = {
  is_desktop: boolean;
  api_base_url: string;
  api_key: string;
  running: boolean;
  healthy: boolean;
  can_start: boolean;
  launched_by_app: boolean;
  error?: string | null;
};

export function isDesktopShell(): boolean {
  if (typeof window === "undefined") return false;
  const w = window as Window & {
    __TAURI_INTERNALS__?: unknown;
    __TAURI__?: unknown;
  };
  return (
    typeof invoke === "function" &&
    (
      "__TAURI_INTERNALS__" in w ||
      "__TAURI__" in w ||
      /\bTauri\b/i.test(navigator.userAgent)
    )
  );
}

export async function getDesktopServiceStatus(): Promise<DesktopServiceStatus | null> {
  try {
    return await invoke<DesktopServiceStatus>("desktop_service_status");
  } catch {
    return null;
  }
}

export async function startDesktopService(): Promise<DesktopServiceStatus | null> {
  try {
    return await invoke<DesktopServiceStatus>("desktop_service_start");
  } catch {
    return null;
  }
}

export async function pickDesktopDemoFile(): Promise<string | null> {
  try {
    return await invoke<string | null>("desktop_pick_demo_file");
  } catch {
    return null;
  }
}

export async function openExternalUrl(url: string): Promise<boolean> {
  try {
    return await invoke<boolean>("desktop_open_external_url", { url });
  } catch {
    return false;
  }
}
