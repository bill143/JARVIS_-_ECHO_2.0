import { NextResponse } from "next/server";
import { getFirmBySlug } from "@/lib/firms";

// GET /api/compare?a=slug&b=slug — two firms for side-by-side comparison.
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const aSlug = searchParams.get("a");
  const bSlug = searchParams.get("b");

  if (!aSlug || !bSlug) {
    return NextResponse.json(
      { error: "Both 'a' and 'b' query params are required." },
      { status: 400 },
    );
  }

  const [a, b] = await Promise.all([
    getFirmBySlug(aSlug),
    getFirmBySlug(bSlug),
  ]);

  if (!a || !b) {
    return NextResponse.json(
      { error: "One or both firms were not found." },
      { status: 404 },
    );
  }

  return NextResponse.json({ a, b });
}
