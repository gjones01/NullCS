import { NextRequest } from "next/server";
import { analysisGateway } from "@/lib/analysis-gateway";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 30;

type Context = { params: Promise<{ segments?: string[] }> };
export async function GET(request: NextRequest, context: Context) {
  return analysisGateway(request, (await context.params).segments || []);
}
export async function POST(request: NextRequest, context: Context) {
  return analysisGateway(request, (await context.params).segments || []);
}
