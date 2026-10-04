import { labels } from "@/lib/labels";
import { CAMPAIGN_TYPES, CHANNELS, GENDERS } from "@/lib/schemas/prediction";

/** Un problème trouvé dans le fichier : ligne (1 = en-tête), colonne et phrase lisible. */
export type CsvProblem = { row: number; column: string; message: string };

export type CsvCheck = {
  /** Nombre de lignes de données lues. */
  rows: number;
  /** Les 100 premiers problèmes. */
  problems: CsvProblem[];
  /** Nombre total de problèmes (au-delà de 100, seuls les 100 premiers sont listés). */
  total: number;
};

export const MAX_LISTED_PROBLEMS = 100;
export const MAX_CSV_BYTES = 10 * 1024 * 1024;

type Rule =
  | { kind: "int" | "float"; min: number; max: number; exclusiveMin?: boolean }
  | { kind: "rate" }
  | { kind: "enum"; values: readonly string[] }
  | { kind: "text" }
  | { kind: "id" };

/** Colonnes du jeu de départ (LLD 5.1) et leurs bornes (API_SPEC 5.1). */
const COLUMNS: Record<string, Rule> = {
  CustomerID: { kind: "id" },
  Age: { kind: "int", min: 18, max: 100 },
  Gender: { kind: "enum", values: GENDERS },
  Income: { kind: "int", min: 0, max: 100_000_000 },
  CampaignChannel: { kind: "enum", values: CHANNELS },
  CampaignType: { kind: "enum", values: CAMPAIGN_TYPES },
  AdSpend: { kind: "float", min: 0, max: 10_000_000, exclusiveMin: true },
  ClickThroughRate: { kind: "rate" },
  ConversionRate: { kind: "rate" },
  WebsiteVisits: { kind: "int", min: 0, max: 100_000_000 },
  PagesPerVisit: { kind: "float", min: 0, max: 1000 },
  TimeOnSite: { kind: "float", min: 0, max: 1440 },
  SocialShares: { kind: "int", min: 0, max: 10_000_000 },
  EmailOpens: { kind: "int", min: 0, max: 10_000_000 },
  EmailClicks: { kind: "int", min: 0, max: 10_000_000 },
  PreviousPurchases: { kind: "int", min: 0, max: 10_000 },
  LoyaltyPoints: { kind: "int", min: 0, max: 10_000_000 },
  AdvertisingPlatform: { kind: "text" },
  AdvertisingTool: { kind: "text" },
  Conversion: { kind: "enum", values: ["0", "1"] },
};

/** Lecture CSV (RFC 4180 simplifiée) : guillemets, virgules et retours à la ligne dans un champ entre guillemets. */
export function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let quoted = false;
  const source = text.charCodeAt(0) === 0xfeff ? text.slice(1) : text;
  for (let i = 0; i < source.length; i += 1) {
    const char = source[i];
    if (quoted) {
      if (char === '"' && source[i + 1] === '"') {
        cell += '"';
        i += 1;
      } else if (char === '"') {
        quoted = false;
      } else {
        cell += char;
      }
    } else if (char === '"') {
      quoted = true;
    } else if (char === ",") {
      row.push(cell);
      cell = "";
    } else if (char === "\n" || char === "\r") {
      if (char === "\r" && source[i + 1] === "\n") {
        i += 1;
      }
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
    } else {
      cell += char;
    }
  }
  if (cell !== "" || row.length > 0) {
    row.push(cell);
    rows.push(row);
  }
  return rows.filter((r) => r.some((c) => c.trim() !== ""));
}

const c = labels.data.csv;

function checkCell(rule: Rule, raw: string, seenIds: Set<string>): string | null {
  const value = raw.trim();
  if (value === "") {
    return c.required;
  }
  switch (rule.kind) {
    case "id": {
      if (!/^\d+$/.test(value) || Number(value) < 1) {
        return c.wholeFrom1;
      }
      if (seenIds.has(value)) {
        return c.duplicate(value);
      }
      seenIds.add(value);
      return null;
    }
    case "int":
    case "float": {
      const number = Number(value);
      if (!Number.isFinite(number)) {
        return c.number;
      }
      if (rule.kind === "int" && !Number.isInteger(number)) {
        return c.whole;
      }
      if (rule.exclusiveMin && number <= rule.min) {
        return c.greater(rule.min);
      }
      if (number < rule.min || number > rule.max) {
        return c.between(rule.min, rule.max);
      }
      return null;
    }
    case "rate": {
      const number = Number(value);
      if (!Number.isFinite(number)) {
        return c.number;
      }
      return number < 0 || number > 1 ? c.fraction(value) : null;
    }
    case "enum":
      return rule.values.includes(value)
        ? null
        : c.unknown(value, rule.values.join(", ").replace(/, ([^,]*)$/, " or $1"));
    case "text": {
      if (/^[=+\-@]/.test(value)) {
        return c.formula(value[0] ?? "");
      }
      return value.length > 100 ? c.tooLong : null;
    }
  }
}

/**
 * Contrôle un fichier CSV du jeu d'agence avant tout envoi : colonnes du jeu de départ, bornes, valeurs permises,
 * numéros uniques, aucune formule. Renvoie les 100 premiers problèmes et leur nombre total.
 */
export function checkCsv(text: string): CsvCheck {
  const table = parseCsv(text);
  const problems: CsvProblem[] = [];
  let total = 0;
  const add = (row: number, column: string, message: string) => {
    total += 1;
    if (problems.length < MAX_LISTED_PROBLEMS) {
      problems.push({ row, column, message });
    }
  };

  const header = (table[0] ?? []).map((name) => name.trim());
  const missing = Object.keys(COLUMNS).filter((name) => !header.includes(name));
  if (header.length === 0 || missing.length === Object.keys(COLUMNS).length) {
    add(1, "—", c.noHeader);
    return { rows: 0, problems, total };
  }
  for (const name of missing) {
    add(1, name, c.missing);
  }
  if (missing.length > 0) {
    return { rows: Math.max(table.length - 1, 0), problems, total };
  }

  const seenIds = new Set<string>();
  const dataRows = table.slice(1);
  dataRows.forEach((cells, index) => {
    const rowNumber = index + 2;
    for (const [name, rule] of Object.entries(COLUMNS)) {
      const message = checkCell(rule, cells[header.indexOf(name)] ?? "", seenIds);
      if (message) {
        add(rowNumber, name, message);
      }
    }
  });
  if (dataRows.length === 0) {
    add(2, "—", c.noRows);
  }
  return { rows: dataRows.length, problems, total };
}
