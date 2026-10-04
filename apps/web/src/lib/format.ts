const formatter = new Intl.DateTimeFormat("en-GB", {
  timeZone: "UTC",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

/** Date et heure en UTC (« 2026-10-03 14:05 UTC »), identiques quel que soit le fuseau du navigateur. Entrée invalide : renvoyée telle quelle. */
export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  const parts = Object.fromEntries(
    formatter.formatToParts(date).map((part) => [part.type, part.value]),
  );
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute} UTC`;
}

/** Taux en pourcentage (« 0.1210 » -> « 12.10% »). */
export function formatPercent(rate: number): string {
  return `${(rate * 100).toFixed(2)}%`;
}

/** Montant en dollars (« 3397.87 » -> « $3,397.87 »). */
export function formatMoney(amount: number): string {
  return `$${amount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
