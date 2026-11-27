// Lấy dữ liệu lịch của một ngày từ CHÍNH dữ liệu web Linh Cơ (cùng bộ tính với app).
// Dùng: node --experimental-strip-types day.mjs [YYYY-MM-DD] > day.json   (mặc định: ngày mai theo giờ Việt Nam)
// DATA_BASE: thư mục dữ liệu (mặc định https://linhco.vn/data, hoặc đường dẫn web/public/data khi chạy cục bộ).
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join, dirname } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const base = process.env.DATA_BASE || "https://linhco.vn/data";
const realFetch = globalThis.fetch;
globalThis.fetch = async (u) => {
  const rel = String(u).replace(/^\/data/, "");
  if (/^https?:/.test(base)) return realFetch(base + rel);
  return { ok: true, json: async () => JSON.parse(readFileSync(join(base, rel), "utf8")) };
};
const A = await import(join(here, "../../web/src/lib/almanac.ts"));

let target = process.argv[2];
if (!target) {
  const now = new Date(Date.now() + 7 * 3600_000 + 24 * 3600_000); // ngày mai, giờ Việt Nam
  target = now.toISOString().slice(0, 10);
}
const [y, m, d] = target.split("-").map(Number);
const day = await A.day(d, m, y);
if (!day) { console.error("Không có dữ liệu cho ngày", target); process.exit(1); }
process.stdout.write(JSON.stringify({ iso: target, ...day }, null, 1));
