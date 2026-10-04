import { labels } from "@/lib/labels";

/** `ad_spend` -> « Ad spend (USD) » (glossaire du PRD) ; un champ inconnu reste tel quel. */
export function fieldLabel(field: string): string {
  const key = field.replace(/_([a-z])/g, (_, letter: string) => letter.toUpperCase());
  const known = (labels.glossary as Record<string, string>)[key];
  return known ?? field;
}

/** Même libellé sans l'unité entre parenthèses (« Ad spend »), pour les listes de facteurs et de conseils. */
export function fieldLabelShort(field: string): string {
  return fieldLabel(field).replace(/ \(.*\)/, "");
}
