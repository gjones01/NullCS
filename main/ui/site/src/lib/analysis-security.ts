import { createHmac, randomBytes, timingSafeEqual } from "node:crypto";

export const SESSION_COOKIE = "nullcs_analysis_session";
export const SESSION_SECONDS = 30 * 24 * 60 * 60;

export function signSession(owner: string, secret: string, expires: number): string {
  const payload = `${owner}.${expires}`;
  return `${payload}.${createHmac("sha256", secret).update(payload).digest("hex")}`;
}

export function newSession(secret: string): string {
  return signSession(randomBytes(32).toString("hex"), secret, Math.floor(Date.now() / 1000) + SESSION_SECONDS);
}

export function sessionOwner(value: string, secret: string): string | null {
  const match = /^([a-f0-9]{64})\.(\d{10})\.([a-f0-9]{64})$/.exec(value);
  if (!match || Number(match[2]) <= Date.now() / 1000) return null;
  const expected = signSession(match[1], secret, Number(match[2])).split(".")[2];
  return timingSafeEqual(Buffer.from(match[3], "hex"), Buffer.from(expected, "hex")) ? match[1] : null;
}

export function permittedPath(parts: string[], method: string): string | null {
  if (!parts.length && method === "POST") return "";
  if (parts.length === 1 && parts[0] === "capabilities" && method === "GET") return "/capabilities";
  if (!/^TEST_\d{14}_[a-f0-9]{32}$/.test(parts[0] || "")) return null;
  if (parts.length === 2 && ["status", "results"].includes(parts[1]) && method === "GET") return `/${parts.join("/")}`;
  if (parts[1] !== "players" || !/^\d{1,20}$/.test(parts[2] || "")) return null;
  if (parts.length === 4 && ((parts[3] === "explain" && method === "POST") || (parts[3] === "explanation" && method === "GET"))) return `/${parts.join("/")}`;
  if (parts.length === 5 && parts[3] === "evidence" && /^evidence_[A-Za-z0-9_-]{1,80}\.csv$/.test(parts[4]) && method === "GET") return `/${parts.join("/")}`;
  return null;
}
