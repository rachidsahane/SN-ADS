"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useId, useState } from "react";
import { useForm } from "react-hook-form";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { classifyAuthError } from "@/lib/auth-errors";
import { labels } from "@/lib/labels";
import { safeNextPath } from "@/lib/redirect";
import { type LoginValues, loginSchema } from "@/lib/schemas/auth";
import { getBrowserSupabase } from "@/lib/supabase/browser";

/** Écran « Sign in » : jamais de détail sur la cause d'un refus (pas de fuite d'existence de compte). */
export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [formError, setFormError] = useState<string | null>(null);
  const ids = useId();
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({ resolver: zodResolver(loginSchema) });

  // `session_expired` reste ignoré jusqu'à la phase 15.
  const reason = searchParams.get("reason");
  const notice =
    reason === "invalid_link"
      ? labels.auth.invalidLink
      : reason === "disabled"
        ? labels.auth.accountDisabled
        : null;
  const alertText = formError ?? notice;

  async function onSubmit(values: LoginValues) {
    setFormError(null);
    try {
      const { error } = await getBrowserSupabase().auth.signInWithPassword(values);
      if (error) {
        const kind = classifyAuthError(error);
        setFormError(
          kind === "rate_limited"
            ? labels.auth.tooManyRequests
            : kind === "unavailable"
              ? labels.errors.serviceUnavailable
              : kind === "disabled"
                ? labels.auth.accountDisabled
                : labels.auth.signIn.invalidCredentials,
        );
        return;
      }
      router.replace(safeNextPath(searchParams.get("next")));
    } catch {
      setFormError(labels.errors.serviceUnavailable);
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4">
      {alertText ? (
        <Alert variant="destructive" role="alert">
          {alertText}
        </Alert>
      ) : null}
      <div className="flex flex-col gap-1.5">
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
          <p id={`${ids}-email-error`} className="text-sm text-destructive">
            {errors.email.message}
          </p>
        ) : null}
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={`${ids}-password`}>{labels.auth.signIn.password}</Label>
        <Input
          id={`${ids}-password`}
          type="password"
          autoComplete="current-password"
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
      <Button type="submit" disabled={isSubmitting}>
        {isSubmitting ? labels.auth.signIn.submitting : labels.auth.signIn.submit}
      </Button>
      <Link href="/forgot-password" className="text-sm">
        {labels.auth.signIn.forgotLink}
      </Link>
    </form>
  );
}
