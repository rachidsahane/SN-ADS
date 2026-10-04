"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useId, useState } from "react";
import { useForm } from "react-hook-form";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FieldError } from "@/components/ui/field-error";
import { Label } from "@/components/ui/label";
import { classifyAuthError } from "@/lib/auth-errors";
import { labels } from "@/lib/labels";
import { type ForgotPasswordValues, forgotPasswordSchema } from "@/lib/schemas/auth";
import { getBrowserSupabase } from "@/lib/supabase/browser";

/**
 * Écran « Forgot password » : la confirmation est la même que le compte existe ou non, et aussi après un 429
 * (qui n'arrive que pour un compte existant) : aucune fuite d'existence de compte.
 */
export function ForgotPasswordForm() {
  const [sent, setSent] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const ids = useId();
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ForgotPasswordValues>({ resolver: zodResolver(forgotPasswordSchema) });

  async function onSubmit(values: ForgotPasswordValues) {
    setFormError(null);
    try {
      const { error } = await getBrowserSupabase().auth.resetPasswordForEmail(values.email);
      if (error && classifyAuthError(error) === "unavailable") {
        setFormError(labels.errors.serviceUnavailable);
        return;
      }
      setSent(true);
    } catch {
      setFormError(labels.errors.serviceUnavailable);
    }
  }

  const backLink = (
    <Link href="/login" className="btn btn-ghost self-start">
      {labels.auth.forgot.backToSignIn}
    </Link>
  );

  if (sent) {
    return (
      <>
        <p className="text-sm">{labels.auth.forgot.sent}</p>
        {backLink}
      </>
    );
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-[14px]">
      {formError ? (
        <Alert
          variant="destructive"
          role="alert"
          className="!border-brand-700 !px-3 !py-2 !text-[13px]"
        >
          {formError}
        </Alert>
      ) : null}
      <div className="field">
        <Label htmlFor={`${ids}-email`}>{labels.auth.signIn.email}</Label>
        <Input
          id={`${ids}-email`}
          type="email"
          autoComplete="email"
          aria-invalid={errors.email ? true : undefined}
          aria-describedby={errors.email ? `${ids}-email-error` : undefined}
          {...register("email")}
        />
        {errors.email ? (
          <FieldError id={`${ids}-email-error`} alert={false}>
            {errors.email.message}
          </FieldError>
        ) : null}
      </div>
      <Button type="submit" blueprint size="lg" className="w-full" disabled={isSubmitting}>
        {isSubmitting ? labels.auth.forgot.submitting : labels.auth.forgot.submit}
      </Button>
      {backLink}
    </form>
  );
}
