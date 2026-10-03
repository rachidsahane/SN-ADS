import { z } from "zod";

import { labels } from "@/lib/labels";

const email = z
  .string()
  .trim()
  .min(1, labels.auth.emailRequired)
  .max(254, labels.auth.emailInvalid)
  .email(labels.auth.emailInvalid);

/** Connexion : aucune règle de longueur sur le mot de passe (celui de l'utilisateur existe déjà). */
export const loginSchema = z.object({
  email,
  password: z.string().min(1, labels.auth.passwordRequired),
});

export const forgotPasswordSchema = z.object({ email });

/** bcrypt (gotrue) refuse plus de 72 OCTETS, pas 72 caractères : un mot de passe accentué ou en emoji pèse plus. */
const MAX_PASSWORD_BYTES = 72;
const utf8Length = (value: string): number => new TextEncoder().encode(value).length;

/** Choix du mot de passe (PRD US-01) : 10 à 72 caractères (72 octets au plus), confirmation identique. */
export const setPasswordSchema = z
  .object({
    password: z
      .string()
      .min(10, labels.auth.setPassword.tooShort)
      .refine((value) => utf8Length(value) <= MAX_PASSWORD_BYTES, labels.auth.setPassword.tooLong),
    confirmation: z.string(),
  })
  .refine((values) => values.password === values.confirmation, {
    message: labels.auth.setPassword.mismatch,
    path: ["confirmation"],
  });

export type LoginValues = z.infer<typeof loginSchema>;
export type ForgotPasswordValues = z.infer<typeof forgotPasswordSchema>;
export type SetPasswordValues = z.infer<typeof setPasswordSchema>;
