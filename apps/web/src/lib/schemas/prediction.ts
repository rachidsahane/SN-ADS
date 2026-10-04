import { z } from "zod";

import { labels } from "@/lib/labels";

export const CHANNELS = ["Social Media", "Email", "PPC", "SEO", "Referral"] as const;
export const CAMPAIGN_TYPES = ["Awareness", "Consideration", "Conversion", "Retention"] as const;
export const GENDERS = ["Male", "Female"] as const;
export const ENGAGEMENT_FIELDS = [
  "pages_per_visit",
  "time_on_site",
  "social_shares",
  "email_opens",
  "email_clicks",
] as const;
export const OPTIONAL_FIELDS = ["advertising_platform", "advertising_tool"] as const;

const MAX_COUNT = 10_000_000;
const e = labels.predict.errors;

function number(min: number, max: number, integer: boolean) {
  const base = z.number({ invalid_type_error: e.number, required_error: e.number });
  const typed = integer ? base.int(e.integer) : base;
  return typed.min(min, e.between(min, max)).max(max, e.between(min, max));
}

const optionalText = z.string().trim().max(100, e.tooLong).optional();

/** Mêmes bornes que l'API (API_SPEC 5.1). Un nombre vide arrive en NaN : message « Enter a number. ». */
const base = z.object({
  campaign_channel: z.enum(CHANNELS),
  campaign_type: z.enum(CAMPAIGN_TYPES),
  ad_spend: z
    .number({ invalid_type_error: e.number, required_error: e.number })
    .gt(0, e.spend(10_000_000))
    .max(10_000_000, e.spend(10_000_000)),
  age: number(18, 100, true),
  gender: z.enum(GENDERS),
  income: number(0, 100_000_000, true),
  previous_purchases: number(0, 10_000, true),
  loyalty_points: number(0, MAX_COUNT, true),
  pages_per_visit: number(0, 1000, false),
  time_on_site: number(0, 1440, false),
  social_shares: number(0, MAX_COUNT, true),
  email_opens: number(0, MAX_COUNT, true),
  email_clicks: number(0, MAX_COUNT, true),
  advertising_platform: optionalText,
  advertising_tool: optionalText,
});

/** Formulaire de campagne ; `required` : champs facultatifs que le modèle actif utilise. */
export function makePredictSchema(required: readonly string[] = []) {
  return base.superRefine((values, context) => {
    for (const field of OPTIONAL_FIELDS) {
      if (required.includes(field) && !values[field]) {
        context.addIssue({ code: z.ZodIssueCode.custom, path: [field], message: e.required });
      }
    }
  });
}

export type PredictValues = z.infer<typeof base>;

/** Corps envoyé à l'API : les champs facultatifs vides sont omis. */
export function toRequestBody(values: PredictValues): PredictValues {
  const body = { ...values };
  for (const field of OPTIONAL_FIELDS) {
    if (!body[field]) {
      delete body[field];
    }
  }
  return body;
}
