import type { Metadata } from "next";

import { AuditTable } from "@/components/admin/audit-table";
import { PageShell } from "@/components/layout/page-shell";
import { labels } from "@/lib/labels";

export const metadata: Metadata = { title: labels.admin.audit.title };

/** Page « Audit log » : journal des actions, lecture seule (PRD US-05). */
export default function AuditPage() {
  return (
    <PageShell>
      <AuditTable />
    </PageShell>
  );
}
