import { NextResponse } from "next/server";
import { getFirmBySlug } from "@/lib/firms";

// GET /api/firms/:slug — single firm by slug.
export async function GET(
  _request: Request,
  { params }: { params: { slug: string } },
) {
  const firm = await getFirmBySlug(params.slug);
  if (!firm) {
    return NextResponse.json({ error: "Firm not found" }, { status: 404 });
  }
  return NextResponse.json({ firm });
}
