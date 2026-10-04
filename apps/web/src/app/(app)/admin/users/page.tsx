import type { Metadata } from "next";

import { UsersTable } from "@/components/admin/users-table";
import { PageShell } from "@/components/layout/page-shell";
import { labels } from "@/lib/labels";

export const metadata: Metadata = { title: labels.admin.users.title };

/** Page « Users » : invitations, rôles et activation des comptes (PRD US-03, US-04). */
export default function UsersPage() {
  return (
    <PageShell>
      <UsersTable />
    </PageShell>
  );
}
