import type { Metadata } from "next";

import { AuthShell } from "@/components/auth/auth-shell";
import { SetPasswordForm } from "@/components/auth/set-password-form";
import { labels } from "@/lib/labels";

export const metadata: Metadata = { title: labels.auth.setPassword.title };

export default function SetPasswordPage() {
  return (
    <AuthShell title={labels.auth.setPassword.title}>
      <SetPasswordForm />
    </AuthShell>
  );
}
