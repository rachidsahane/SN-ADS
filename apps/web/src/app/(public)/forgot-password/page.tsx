import type { Metadata } from "next";

import { AuthShell } from "@/components/auth/auth-shell";
import { ForgotPasswordForm } from "@/components/auth/forgot-password-form";
import { labels } from "@/lib/labels";

export const metadata: Metadata = { title: labels.auth.forgot.title };

export default function ForgotPasswordPage() {
  return (
    <AuthShell title={labels.auth.forgot.title}>
      <ForgotPasswordForm />
    </AuthShell>
  );
}
