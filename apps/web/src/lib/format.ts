/**
 * Date et heure du prototype (« Oct 4, 2026, 10:09 ») : anglais, 24 h, sans secondes, dans le fuseau du navigateur.
 * Entrée invalide : renvoyée telle quelle.
 */
export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
}

/** Taux en pourcentage (« 0.1210 » -> « 12.10% »). */
export function formatPercent(rate: number): string {
  return `${(rate * 100).toFixed(2)}%`;
}

/** Montant en dollars (« 3397.87 » -> « $3,397.87 »), `decimals` chiffres après la virgule (2 par défaut). */
export function formatMoney(amount: number, decimals = 2): string {
  return `$${amount.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`;
}

/** Nombre de visites, une décimale (« 23.54 » -> « 23.5 »). */
export function formatVisits(visits: number): string {
  return visits.toFixed(1);
}

/** Entier ou décimal avec séparateurs de milliers anglais (« 65000 » -> « 65,000 »). */
export function formatNumber(value: number): string {
  return value.toLocaleString("en-US");
}

const MINUS = "−";

/**
 * Contribution d'un facteur (prototype) : taux en points de pourcentage x100 (« +0.12 pp »), visites en nombre
 * (« −0.30 »). Vrai signe moins.
 */
export function formatContribution(value: number, kind: "rate" | "count"): string {
  const sign = value >= 0 ? "+" : MINUS;
  return kind === "rate"
    ? `${sign}${Math.abs(value * 100).toFixed(2)} pp`
    : `${sign}${Math.abs(value).toFixed(2)}`;
}

/** Part en pourcentage entier (« 0.14 » -> « 14% »). */
export function formatShare(share: number): string {
  return `${(share * 100).toFixed(0)}%`;
}
