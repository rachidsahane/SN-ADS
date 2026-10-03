import type { Metadata } from "next";
import { Suspense } from "react";

import { AuthShell } from "@/components/auth/auth-shell";
import { LoginForm } from "@/components/auth/login-form";
import { labels } from "@/lib/labels";

export const metadata: Metadata = { title: labels.auth.signIn.title };

export default function LoginPage() {
  return (
    <AuthShell title={labels.auth.signIn.title}>
      <Suspense>
        <LoginForm />
      </Suspense>
    </AuthShell>
  );
}
