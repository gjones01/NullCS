import "server-only";
import { NextRequest, NextResponse } from "next/server";
import { newSession, permittedPath, SESSION_COOKIE, SESSION_SECONDS, sessionOwner } from "./analysis-security";

function error(status: number, message: string, code: string) {
  return NextResponse.json({ error: { code, message } }, { status, headers: { "Cache-Control": "no-store" } });
}

function workerUrl(value: string): string {
  const url = new URL(value);
  if (url.username || url.password || url.search || url.hash || url.pathname !== "/") throw new Error("Invalid worker URL");
  if (url.protocol !== "https:" && !(url.protocol === "http:" && ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname))) throw new Error("HTTPS worker required");
  return url.origin;
}

async function smallBody(request: NextRequest): Promise<string> {
  if (!request.headers.get("content-type")?.startsWith("application/json")) throw new Error("Expected JSON metadata");
  const reader = request.body?.getReader();
  if (!reader) throw new Error("Missing upload metadata");
  const chunks: Uint8Array[] = [];
  let length = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    length += value.byteLength;
    if (length > 4096) { await reader.cancel(); throw new Error("Metadata is too large"); }
    chunks.push(value);
  }
  const parsed: unknown = JSON.parse(Buffer.concat(chunks).toString("utf8"));
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("Invalid metadata");
  const data = parsed as Record<string, unknown>;
  if (Object.keys(data).some((key) => !["filename", "size"].includes(key)) || typeof data.filename !== "string" || typeof data.size !== "number" || !Number.isSafeInteger(data.size)) throw new Error("Invalid metadata");
  return JSON.stringify(data);
}

export async function analysisGateway(request: NextRequest, parts: string[]) {
  const path = permittedPath(parts, request.method);
  if (path === null) return error(404, "Analysis endpoint not found", "not_found");
  const secret = process.env.NULLCS_SESSION_SECRET || "";
  const apiKey = process.env.NULLCS_API_KEY || "";
  let base: string, publicBase: string;
  try {
    if (secret.length < 32 || apiKey.length < 32) throw new Error("Missing configuration");
    base = workerUrl(process.env.NULLCS_API_BASE_URL || "");
    publicBase = workerUrl(process.env.NULLCS_WORKER_PUBLIC_URL || base);
  } catch {
    return error(503, "Live analysis is not configured yet. The research pages remain available.", "not_configured");
  }
  if (request.method === "POST" && request.headers.get("origin") !== new URL(request.url).origin) return error(403, "Request origin is not allowed", "origin_rejected");
  let session = request.cookies.get(SESSION_COOKIE)?.value || "";
  let owner = sessionOwner(session, secret);
  if (!owner) {
    if (path !== "" && path !== "/capabilities") return error(401, "This browser session cannot access that analysis.", "session_required");
    session = newSession(secret);
    owner = sessionOwner(session, secret)!;
  }
  let body: string | undefined;
  if (path === "") {
    try { body = await smallBody(request); }
    catch { return error(400, "Send a demo filename and byte size as small JSON metadata. Demo bytes must be uploaded directly to the worker.", "invalid_metadata"); }
  }
  try {
    const upstream = await fetch(`${base}/api/analysis${path}`, {
      method: request.method, body, cache: "no-store", redirect: "error",
      signal: AbortSignal.timeout(20_000),
      headers: { "X-NULLCS-KEY": apiKey, "X-NULLCS-OWNER": owner, "Content-Type": "application/json" },
    });
    // Never return arbitrary proxy/server diagnostics or response headers.
    if (!upstream.headers.get("content-type")?.includes("application/json")) throw new Error("Invalid worker response");
    const data = await upstream.json();
    if (!upstream.ok) {
      const allowed = new Set([400, 401, 403, 404, 409, 413, 415, 422, 429, 503]);
      return error(allowed.has(upstream.status) ? upstream.status : 502,
        typeof data?.error?.message === "string" ? data.error.message : "The analysis service could not complete this request.",
        "worker_request_failed");
    }
    if (path === "") {
      if (!/^TEST_\d{14}_[a-f0-9]{32}$/.test(data.job_id) || data.upload_path !== `/api/analysis/${data.job_id}/upload` || typeof data.upload_token !== "string") throw new Error("Invalid upload ticket");
      data.upload_url = `${publicBase}${data.upload_path}`;
      delete data.upload_path;
    }
    const response = NextResponse.json(data, { headers: { "Cache-Control": "no-store" } });
    response.cookies.set(SESSION_COOKIE, session, {
      httpOnly: true, secure: new URL(request.url).protocol === "https:", sameSite: "strict", path: "/", maxAge: SESSION_SECONDS,
    });
    return response;
  } catch {
    return error(503, "The analysis worker is unavailable. Please try again shortly.", "worker_unavailable");
  }
}
