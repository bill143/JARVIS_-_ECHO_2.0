import { NextResponse } from "next/server";
import { getFirms } from "@/lib/firms";

// GET /api/firms — list all firms (ranked).
export async function GET() {
  const firms = await getFirms();
  return NextResponse.json({ firms });
}
