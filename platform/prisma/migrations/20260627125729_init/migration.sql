-- CreateTable
CREATE TABLE "Firm" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "slug" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "logoUrl" TEXT,
    "rank" INTEGER,
    "rating" REAL,
    "legalEntity" TEXT,
    "hq" TEXT,
    "ceo" TEXT,
    "incorporated" TEXT,
    "summary" TEXT,
    "reviewBody" TEXT,
    "platforms" TEXT NOT NULL,
    "liquidity" TEXT,
    "websiteUrl" TEXT,
    "affiliateUrl" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable
CREATE TABLE "Plan" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "firmId" TEXT NOT NULL,
    "challenge" TEXT NOT NULL,
    "minAccount" INTEGER NOT NULL,
    "maxAccount" INTEGER NOT NULL,
    "profitSplit" INTEGER,
    CONSTRAINT "Plan_firmId_fkey" FOREIGN KEY ("firmId") REFERENCES "Firm" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Coupon" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "firmId" TEXT NOT NULL,
    "code" TEXT NOT NULL,
    "percent" INTEGER,
    "note" TEXT,
    "expiresAt" DATETIME,
    CONSTRAINT "Coupon_firmId_fkey" FOREIGN KEY ("firmId") REFERENCES "Firm" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Tag" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "slug" TEXT NOT NULL,
    "label" TEXT NOT NULL
);

-- CreateTable
CREATE TABLE "_FirmTags" (
    "A" TEXT NOT NULL,
    "B" TEXT NOT NULL,
    CONSTRAINT "_FirmTags_A_fkey" FOREIGN KEY ("A") REFERENCES "Firm" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "_FirmTags_B_fkey" FOREIGN KEY ("B") REFERENCES "Tag" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateIndex
CREATE UNIQUE INDEX "Firm_slug_key" ON "Firm"("slug");

-- CreateIndex
CREATE UNIQUE INDEX "Tag_slug_key" ON "Tag"("slug");

-- CreateIndex
CREATE UNIQUE INDEX "_FirmTags_AB_unique" ON "_FirmTags"("A", "B");

-- CreateIndex
CREATE INDEX "_FirmTags_B_index" ON "_FirmTags"("B");
