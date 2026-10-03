import type { Metadata } from "next";

import { UsersTable } from "@/components/admin/users-table";
import { PageTitle } from "@/components/layout/page-title";
import { labels } from "@/lib/labels";

export const metadata: Metadata = { title: labels.admin.users.title };

/** Page « Users » : le bouton d'invitation et le tableau vivent dans `UsersTable`. */
export default function UsersPage() {
  return (
    <>
      <PageTitle>{labels.admin.users.title}</PageTitle>
      <UsersTable />
    </>
  );
}
