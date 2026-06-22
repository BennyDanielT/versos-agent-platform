// Server-side proxy to the FastAPI backend.
//
// Why a proxy and not fetch-from-browser: the browser only ever talks to this Next.js
// server, which forwards to the backend. That keeps the backend URL off the client,
// sidesteps CORS, and is the natural place to add auth headers / rate limiting later.
// The backend URL lives in BACKEND_URL (server env), never shipped to the client.
import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8090";

async function forward(req: NextRequest, path: string[]) {
  const target = `${BACKEND_URL}/${path.join("/")}${req.nextUrl.search}`;
  const init: RequestInit = {
    method: req.method,
    headers: { "content-type": "application/json" },
    // GET/HEAD must not carry a body.
    body: ["GET", "HEAD"].includes(req.method) ? undefined : await req.text(),
    cache: "no-store",
  };
  try {
    const res = await fetch(target, init);
    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: { "content-type": res.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    // Backend down / unreachable -> a clean 502 the UI can render, not a crash.
    return NextResponse.json(
      { detail: `Backend unreachable at ${BACKEND_URL}` },
      { status: 502 },
    );
  }
}

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(req: NextRequest, ctx: Ctx) {
  return forward(req, (await ctx.params).path);
}
export async function POST(req: NextRequest, ctx: Ctx) {
  return forward(req, (await ctx.params).path);
}
export async function PUT(req: NextRequest, ctx: Ctx) {
  return forward(req, (await ctx.params).path);
}
