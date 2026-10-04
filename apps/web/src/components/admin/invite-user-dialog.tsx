"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useId, useState } from "react";
import { useForm } from "react-hook-form";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { FieldError } from "@/components/ui/field-error";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { useInviteUser } from "@/hooks/use-admin-users";
import { ApiError } from "@/lib/api/client";
import { apiMessage, isUnexpectedError } from "@/lib/api/messages";
import { labels } from "@/lib/labels";
import { reportError } from "@/lib/observability";
import { type InviteValues, inviteSchema } from "@/lib/schemas/admin";

type InviteUserDialogProps = {
  open: boolean;
  onClose: () => void;
  /** Appelé avec l'adresse invitée une fois l'invitation envoyée. */
  onInvited: (email: string) => void;
};

/** Fenêtre « Invite user » (PRD US-03). Le formulaire n'existe que fenêtre ouverte : il repart vide à chaque ouverture. */
export function InviteUserDialog({ open, onClose, onInvited }: InviteUserDialogProps) {
  return (
    <Dialog open={open} onClose={onClose} title={labels.admin.invite.title}>
      <InviteForm onClose={onClose} onInvited={onInvited} />
    </Dialog>
  );
}

function InviteForm({
  onClose,
  onInvited,
}: {
  onClose: () => void;
  onInvited: (email: string) => void;
}) {
  const ids = useId();
  const invite = useInviteUser();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<InviteValues>({
    resolver: zodResolver(inviteSchema),
    defaultValues: { email: "", fullName: "", role: "marketer" },
  });

  async function onSubmit(values: InviteValues) {
    setFormError(null);
    const email = values.email.toLowerCase();
    try {
      await invite.mutateAsync({ email, full_name: values.fullName, role: values.role });
    } catch (error) {
      if (error instanceof ApiError && error.code === "EMAIL_ALREADY_REGISTERED") {
        setError("email", { type: "server", message: error.message });
        return;
      }
      if (
        error instanceof ApiError &&
        error.code === "VALIDATION_ERROR" &&
        error.details.some((detail) => detail.field === "email")
      ) {
        // Adresse refusée par le serveur d'authentification (plus strict que le formulaire).
        setError("email", { type: "server", message: labels.admin.invite.emailInvalid });
        return;
      }
      if (isUnexpectedError(error)) {
        reportError(error, {
          route: "invite-user-dialog",
          requestId: error instanceof ApiError ? error.requestId : null,
        });
      }
      // Jamais le détail brut d'une erreur 422 : seul le message général de l'API est montré.
      setFormError(apiMessage(error));
      return;
    }
    onInvited(email);
    onClose();
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-[10px]">
      {formError ? (
        <Alert variant="destructive" role="alert" className="!px-3 !py-2 !text-[13px]">
          {formError}
        </Alert>
      ) : null}
      <div className="field">
        <Label htmlFor={`${ids}-email`}>{labels.admin.invite.email}</Label>
        <Input
          id={`${ids}-email`}
          type="email"
          autoComplete="off"
          aria-invalid={errors.email ? true : undefined}
          aria-describedby={errors.email ? `${ids}-email-error` : undefined}
          {...register("email")}
        />
        {errors.email ? (
          <FieldError id={`${ids}-email-error`}>{errors.email.message}</FieldError>
        ) : null}
      </div>
      <div className="field">
        <Label htmlFor={`${ids}-name`}>{labels.admin.invite.fullName}</Label>
        <Input
          id={`${ids}-name`}
          type="text"
          autoComplete="off"
          aria-invalid={errors.fullName ? true : undefined}
          aria-describedby={errors.fullName ? `${ids}-name-error` : undefined}
          {...register("fullName")}
        />
        {errors.fullName ? (
          <FieldError id={`${ids}-name-error`}>{errors.fullName.message}</FieldError>
        ) : null}
      </div>
      <div className="field">
        <Label htmlFor={`${ids}-role`}>{labels.admin.invite.role}</Label>
        <Select id={`${ids}-role`} {...register("role")}>
          <option value="marketer">{labels.admin.users.roles.marketer}</option>
          <option value="admin">{labels.admin.users.roles.admin}</option>
        </Select>
      </div>
      <div className="dialog-actions">
        <Button type="button" variant="outline" onClick={onClose}>
          {labels.admin.invite.cancel}
        </Button>
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? labels.admin.invite.submitting : labels.admin.invite.submit}
        </Button>
      </div>
    </form>
  );
}
