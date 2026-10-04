import { fieldLabelShort } from "@/lib/field-labels";
import { labels } from "@/lib/labels";
import {
  CAMPAIGN_TYPES,
  CHANNELS,
  ENGAGEMENT_FIELDS,
  GENDERS,
  OPTIONAL_FIELDS,
  type PredictValues,
  makePredictSchema,
} from "@/lib/schemas/prediction";

/** Champs du formulaire de campagne, dans l'ordre d'affichage des trois blocs du prototype. */
export const FORM_GROUPS = [
  { key: "plan", fields: ["campaign_channel", "campaign_type", "ad_spend"] },
  {
    key: "audience",
    fields: ["age", "gender", "income", "previous_purchases", "loyalty_points"],
  },
  { key: "engagement", fields: [...ENGAGEMENT_FIELDS] },
] as const;

export type FormField = keyof PredictValues;
export type FormState = Record<string, string>;

export const SELECT_OPTIONS: Record<string, readonly string[]> = {
  campaign_channel: CHANNELS,
  campaign_type: CAMPAIGN_TYPES,
  gender: GENDERS,
};

/** Bornes de l'API (API_SPEC 5.1), reprises du prototype. */
const LIMITS: Record<string, readonly [number, number]> = {
  ad_spend: [0, 10_000_000],
  age: [18, 100],
  income: [0, 100_000_000],
  previous_purchases: [0, 10_000],
  loyalty_points: [0, 10_000_000],
  pages_per_visit: [0, 1000],
  time_on_site: [0, 1440],
  social_shares: [0, 10_000_000],
  email_opens: [0, 10_000_000],
  email_clicks: [0, 10_000_000],
};
const INTEGERS = new Set([
  "age",
  "income",
  "previous_purchases",
  "loyalty_points",
  "social_shares",
  "email_opens",
  "email_clicks",
]);

/** Valeurs de départ (prototype) ; l'engagement est remplacé par les moyennes observées dès qu'elles arrivent. */
export const DEFAULT_FORM: FormState = {
  campaign_channel: "Email",
  campaign_type: "Conversion",
  ad_spend: "5000",
  age: "38",
  gender: "Female",
  income: "65000",
  previous_purchases: "3",
  loyalty_points: "2200",
  pages_per_visit: "5.4",
  time_on_site: "7.6",
  social_shares: "50",
  email_opens: "11",
  email_clicks: "5",
};

/** Formulaire (texte) d'une campagne déjà décrite, par exemple une prédiction enregistrée. */
export function formFromInput(input: Partial<Record<string, unknown>>): FormState {
  const form: FormState = {};
  for (const [name, value] of Object.entries(input)) {
    if (value !== null && value !== undefined) {
      form[name] = String(value);
    }
  }
  return form;
}

export type Ranges = Record<string, Record<string, number>>;

export type ParsedForm = {
  /** Message par champ en erreur. */
  errors: Record<string, string>;
  /** Campagne prête à envoyer, ou `null` tant qu'un champ est invalide. */
  values: PredictValues | null;
  /** Champs valides mais hors des valeurs vues à l'apprentissage (avertissement, pas une erreur). */
  outOfRange: Set<string>;
};

/**
 * Lit le formulaire tel que tapé : espaces et virgules de milliers acceptés, mêmes messages que le prototype.
 * `optionalUsed` : champs facultatifs que le modèle actif utilise (alors obligatoires).
 */
export function parseForm(
  form: FormState,
  optionalUsed: readonly string[] = [],
  ranges: Ranges = {},
): ParsedForm {
  const e = labels.predict.errors;
  const errors: Record<string, string> = {};
  const parsed: Record<string, string | number> = {};
  const outOfRange = new Set<string>();

  for (const [name, options] of Object.entries(SELECT_OPTIONS)) {
    const value = form[name] ?? "";
    if (options.includes(value)) {
      parsed[name] = value;
    } else {
      errors[name] = e.required;
    }
  }

  for (const [name, [min, max]] of Object.entries(LIMITS)) {
    const text = String(form[name] ?? "")
      .trim()
      .replace(/,/g, "");
    if (text === "") {
      errors[name] = e.required;
      continue;
    }
    const number = Number(text);
    if (!Number.isFinite(number)) {
      errors[name] = e.number;
    } else if (INTEGERS.has(name) && !Number.isInteger(number)) {
      errors[name] = e.integer;
    } else if (name === "ad_spend" && number <= 0) {
      errors[name] = e.positive;
    } else if (number < min || number > max) {
      errors[name] = e.range(fieldLabelShort(name), min, max);
    } else {
      parsed[name] = number;
      const range = ranges[name];
      if (range && (number < (range.min ?? -Infinity) || number > (range.max ?? Infinity))) {
        outOfRange.add(name);
      }
    }
  }

  for (const name of OPTIONAL_FIELDS) {
    if (!optionalUsed.includes(name)) {
      continue;
    }
    const text = (form[name] ?? "").trim();
    if (text === "") {
      errors[name] = e.required;
    } else if (text.length > 100) {
      errors[name] = e.tooLong;
    } else {
      parsed[name] = text;
    }
  }

  if (Object.keys(errors).length > 0) {
    return { errors, values: null, outOfRange };
  }
  // Dernier garde-fou : le même schéma Zod que l'API (jamais atteint si les contrôles ci-dessus sont complets).
  const checked = makePredictSchema(optionalUsed).safeParse(parsed);
  if (!checked.success) {
    for (const issue of checked.error.issues) {
      errors[String(issue.path[0] ?? "form")] = issue.message;
    }
    return { errors, values: null, outOfRange };
  }
  return { errors: {}, values: checked.data, outOfRange };
}
