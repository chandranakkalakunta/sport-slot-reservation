/**
 * Generates PWA icons and favicon from the source SlotSense icon.
 * Run from the frontend/ directory: node scripts/gen-icons.mjs
 *
 * Maskable variant: source scaled to 80% of canvas, centered on a
 * navy (#1a4d8f) background — keeps the mark inside the safe-area circle.
 */
import sharp from "sharp";
import { fileURLToPath } from "url";
import path from "path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const publicDir = path.resolve(__dirname, "../public");
const src = path.join(publicDir, "slotsense-icon-source.png");

const NAVY = { r: 26, g: 77, b: 143, alpha: 1 };

async function resize(size, outName) {
  await sharp(src).resize(size, size, { fit: "cover" }).toFile(path.join(publicDir, outName));
  console.log(`✓ ${outName}  ${size}x${size}`);
}

async function maskable(canvasSize, outName) {
  // Scale source to 80% (safe-area inner radius) and composite onto navy canvas
  const innerSize = Math.round(canvasSize * 0.8);
  const offset = Math.round((canvasSize - innerSize) / 2);

  const inner = await sharp(src)
    .resize(innerSize, innerSize, { fit: "cover" })
    .toBuffer();

  await sharp({
    create: { width: canvasSize, height: canvasSize, channels: 4, background: NAVY },
  })
    .composite([{ input: inner, top: offset, left: offset }])
    .png()
    .toFile(path.join(publicDir, outName));
  console.log(`✓ ${outName}  ${canvasSize}x${canvasSize} (maskable, 80% safe-area)`);
}

await resize(192, "pwa-192x192.png");
await resize(512, "pwa-512x512.png");
await resize(32, "favicon-32x32.png");
await maskable(512, "pwa-maskable-512x512.png");
console.log("Done.");
