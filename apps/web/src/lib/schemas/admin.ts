import { z } from "zod";

import { labels } from "@/lib/labels";

/** Invitation d'un utilisateur (PRD US-03) : mêmes bornes que l'API (e-mail 254, nom 1 à 120 caractères). */
export const inviteSchema = z.object({
  email: z
    .string()
    .trim()
    .min(1, labels.admin.invite.emailRequired)
    .max(254, labels.admin.invite.emailTooLong)
    .email(labels.admin.invite.emailInvalid),
  fullName: z
    .string()
    .trim()
    .min(1, labels.admin.invite.nameRequired)
    .max(120, labels.admin.invite.nameTooLong),
  role: z.enum(["marketer", "admin"]),
});

export type InviteValues = z.infer<typeof inviteSchema>;
