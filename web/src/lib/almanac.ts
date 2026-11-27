// Đọc dữ liệu lịch do tools/export (chạy chính core Kotlin của app) xuất ra.
// KHÔNG có công thức lịch ở đây: chỉ tra bảng và giải mã các trường theo `fields`.

export const SCHEMA_VERSION = 1;

export interface Lookup {
  schemaVersion: number;
  core: string;
  range: [number, number];
  fields: string[];
  canChi: string[];
  solarTerm: string[];
  dayGod: string[];
  direction: string[];
  truc: string[];
  trucAdvice: Record<string, [string, string]>;
  chi: string[];
  hourRanges: string[];
  weekdays: string[];
  tamNuong: number[];
  nguyetKy: number[];
}

interface YearFile {
  schemaVersion: number;
  year: number;
  fields: string[];
  days: number[][];
}

export interface Day {
  solar: { day: number; month: number; year: number };
  weekday: string;
  weekdayIndex: number;
  lunar: { day: number; month: number; year: number; leap: boolean };
  dayCanChi: string;
  monthCanChi: string;
  yearCanChi: string;
  solarTerm: string;
  solarTermStart: boolean;
  dayGod: string;
  hoangDao: boolean;
  goodHours: { chi: string; range: string; index: number }[];
  badHours: { chi: string; range: string; index: number }[];
  hyThan: string;
  taiThan: string;
  truc: string;
  shouldDo: string;
  shouldAvoid: string;
  tamNuong: boolean;
  nguyetKy: boolean;
}

const base = (globalThis as any).__LINHCO_DATA__ ?? "/data";
let lookupPromise: Promise<Lookup> | null = null;
const yearCache = new Map<number, Promise<YearFile>>();

async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`Không tải được ${url} (${r.status})`);
  return r.json() as Promise<T>;
}

export function lookup(): Promise<Lookup> {
  lookupPromise ??= getJson<Lookup>(`${base}/lookup.json`).then((l) => {
    if (l.schemaVersion !== SCHEMA_VERSION) throw new Error(`Dữ liệu lịch phiên bản ${l.schemaVersion}, web cần ${SCHEMA_VERSION}`);
    return l;
  });
  return lookupPromise;
}

function yearFile(year: number): Promise<YearFile> {
  let p = yearCache.get(year);
  if (!p) {
    p = getJson<YearFile>(`${base}/years/${year}.json`);
    yearCache.set(year, p);
  }
  return p;
}

export function inRange(l: Lookup, year: number): boolean {
  return year >= l.range[0] && year <= l.range[1];
}

/** Giải mã một hàng theo tên trường (không phụ thuộc vị trí cứng). */
export function decode(l: Lookup, fields: string[], row: number[], year: number): Day {
  const f = (name: string) => {
    const i = fields.indexOf(name);
    if (i < 0) throw new Error(`Thiếu trường ${name}`);
    return row[i];
  };
  const mask = f("goodHoursMask");
  const hours = l.chi.map((chi, index) => ({ chi, range: l.hourRanges[index], index }));
  const truc = l.truc[f("truc")];
  const advice = l.trucAdvice[truc] ?? ["", ""];
  const weekdayIndex = f("weekday");
  return {
    solar: { day: f("solarDay"), month: f("solarMonth"), year },
    weekday: l.weekdays[weekdayIndex],
    weekdayIndex,
    lunar: { day: f("lunarDay"), month: f("lunarMonth"), year: f("lunarYear"), leap: f("lunarLeap") === 1 },
    dayCanChi: l.canChi[f("dayCanChi")],
    monthCanChi: l.canChi[f("monthCanChi")],
    yearCanChi: l.canChi[f("yearCanChi")],
    solarTerm: l.solarTerm[f("solarTerm")],
    solarTermStart: f("solarTermStart") === 1,
    dayGod: l.dayGod[f("dayGod")],
    hoangDao: f("hoangDao") === 1,
    goodHours: hours.filter((h) => (mask >> h.index) & 1),
    badHours: hours.filter((h) => !((mask >> h.index) & 1)),
    hyThan: l.direction[f("hyThan")],
    taiThan: l.direction[f("taiThan")],
    truc,
    shouldDo: advice[0],
    shouldAvoid: advice[1],
    tamNuong: f("tamNuong") === 1,
    nguyetKy: f("nguyetKy") === 1,
  };
}

export async function yearDays(year: number): Promise<Day[]> {
  const l = await lookup();
  if (!inRange(l, year)) throw new RangeError(`Lịch chỉ hỗ trợ năm ${l.range[0]}–${l.range[1]}`);
  const y = await yearFile(year);
  if (y.schemaVersion !== SCHEMA_VERSION) throw new Error("Sai phiên bản dữ liệu năm");
  return y.days.map((r) => decode(l, y.fields, r, year));
}

export async function day(d: number, m: number, y: number): Promise<Day | undefined> {
  return (await yearDays(y)).find((x) => x.solar.day === d && x.solar.month === m);
}

export async function monthDays(m: number, y: number): Promise<Day[]> {
  return (await yearDays(y)).filter((x) => x.solar.month === m);
}

/** Tìm ngày dương ứng với ngày âm (tra ngược trong file năm). Không có thì trả undefined. */
export async function lunarToSolar(ld: number, lm: number, ly: number, leap: boolean): Promise<Day | undefined> {
  const l = await lookup();
  for (const y of [ly, ly + 1]) {
    if (!inRange(l, y)) continue;
    const hit = (await yearDays(y)).find(
      (x) => x.lunar.day === ld && x.lunar.month === lm && x.lunar.year === ly && x.lunar.leap === leap,
    );
    if (hit) return hit;
  }
  return undefined;
}

const MONTH_NAMES: Record<number, string> = { 1: "Giêng", 11: "Một", 12: "Chạp" };

/** Cách đọc ngày âm giống app: "mùng 5 tháng Giêng", "15 tháng Chạp nhuận". */
export function lunarText(d: Day): string {
  const day = d.lunar.day <= 10 ? `mùng ${d.lunar.day}` : `${d.lunar.day}`;
  const month = MONTH_NAMES[d.lunar.month] ?? String(d.lunar.month);
  return `${day} tháng ${month}${d.lunar.leap ? " nhuận" : ""}`;
}

export function todayVN(): { day: number; month: number; year: number } {
  // Ngày hiện tại theo giờ Việt Nam, không phụ thuộc múi giờ máy người xem.
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Ho_Chi_Minh", year: "numeric", month: "2-digit", day: "2-digit" })
    .format(new Date())
    .split("-")
    .map(Number);
  return { year: parts[0], month: parts[1], day: parts[2] };
}

export function hourVN(): number {
  return Number(new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Ho_Chi_Minh", hour: "2-digit", hourCycle: "h23" }).format(new Date()));
}

/** Chỉ số chi của giờ hiện tại (giờ Tý 23h–1h …), giống CanChi.hourChiOf của core. */
export function hourChiIndex(hour: number): number {
  return Math.floor((hour + 1) / 2) % 12;
}

export function pad(n: number): string {
  return String(n).padStart(2, "0");
}

export function iso(d: { day: number; month: number; year: number }): string {
  return `${d.year}-${pad(d.month)}-${pad(d.day)}`;
}

export function parseIso(s: string | null): { day: number; month: number; year: number } | null {
  const m = s?.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  return m ? { year: +m[1], month: +m[2], day: +m[3] } : null;
}
