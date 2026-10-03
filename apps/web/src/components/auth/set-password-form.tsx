"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useId, useState } from "react";
import { useForm } from "react-hook-form";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { classifyAuthError } from "@/lib/auth-errors";
import { labels } from "@/lib/labels";
import { type SetPasswordValues, setPasswordSchema } from "@/lib/schemas/auth";
import { getBrowserSupabase } from "@/lib/supabase/browser";

/** Écran « Set your password » : atteint après /auth/confirm, qui a créé la session. */
export function SetPasswordForm() {
  const router = useRouter();
  const [formError, setFormError] = useState<string | null>(null);
  const ids = useId();
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<SetPasswordValues>({ resolver: zodResolver(setPasswordSchema) });

  async function onSubmit(values: SetPasswordValues) {
    setFormError(null);
    try {
      const { error } = await getBrowserSupabase().auth.updateUser({ password: values.password });
      if (!error) {
        router.replace("/predict");
        return;
      }
      if (error.name === "AuthSessionMissingError") {
        router.replace("/login?reason=invalid_link");
      } else if (error.code === "weak_password") {
        setFormError(labels.auth.setPassword.tooShort);
      } else if (error.code === "same_password") {
        setFormError(labels.auth.setPassword.samePassword);
      } else if (classifyAuthError(error) === "unavailable") {
        setFormError(labels.errors.serviceUnavailable);
      } else {
        setFormError(labels.errors.generic);
      }
    } catch {
      setFormError(labels.errors.serviceUnavailable);
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4">
      {formError ? (
        <Alert variant="destructive" role="alert">
          {formError}
        </Alert>
      ) : null}
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={`${ids}-password`}>{labels.auth.setPassword.password}</Label>
        <Input
          id={`${ids}-password`}
          type="password"
          autoComplete="new-password"
          aria-invalid={errors.password ? true : undefined}
          aria-describedby={errors.password ? `${ids}-password-error` : undefined}
          {...register("password")}
        />
        {errors.password ? (
          <p id={`${ids}-password-error`} className="text-sm text-destructive">
            {errors.password.message}
          </p>
        ) : null}
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={`${ids}-confirmation`}>{labels.auth.setPassword.confirmation}</Label>
        <Input
          id={`${ids}-confirmation`}
          type="password"
          autoComplete="new-password"
          aria-invalid={errors.confirmation ? true : undefined}
          aria-describedby={errors.confirmation ? `${ids}-confirmation-error` : undefined}
          {...register("confirmation")}
        />
        {errors.confirmation ? (
          <p id={`${ids}-confirmation-error`} className="text-sm text-destructive">
            {errors.confirmation.message}
          </p>
        ) : null}
      </div>
      <Button type="submit" disabled={isSubmitting}>
        {isSubmitting ? labels.auth.setPassword.submitting : labels.auth.setPassword.submit}
      </Button>
    </form>
  );
}
