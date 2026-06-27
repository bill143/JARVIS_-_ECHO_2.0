import { NextResponse } from "next/server";
import { getOffers } from "@/lib/firms";

// GET /api/offers — all active coupons across firms.
export async function GET() {
  const offers = await getOffers();
  return NextResponse.json({ offers });
}
