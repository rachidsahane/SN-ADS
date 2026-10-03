"use client";

import { useEffect, useState } from "react";

import { InviteUserDialog } from "@/components/admin/invite-user-dialog";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { type AdminUser, useAdminUsers, useUpdateUser } from "@/hooks/use-admin-users";
import { useMe } from "@/hooks/use-me";
import { ApiError } from "@/lib/api/client";
import { apiMessage, isUnexpectedError } from "@/lib/api/messages";
import { labels } from "@/lib/labels";
import { reportError } from "@/lib/observability";

type Role = AdminUser["role"];

/** Tableau des utilisateurs (PRD US-03, US-04) : rôle, activation, invitation. Tout texte venu des données est affiché comme texte. */
export function UsersTable() {
  const { data: me } = useMe();
  const users = useAdminUsers();
  const [inviteOpen, setInviteOpen] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const rows = users.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <div className="mt-4 flex flex-col gap-4">
      <div className="flex justify-end">
        <Button onClick={() => setInviteOpen(true)}>{labels.admin.users.invite}</Button>
      </div>
      <InviteUserDialog
        open={inviteOpen}
        onClose={() => setInviteOpen(false)}
        onInvited={(email) => {
          setActionError(null);
          setNotice(labels.admin.users.invitedNotice(email));
        }}
      />
      {notice ? (
        <Alert variant="success" role="status">
          {notice}
        </Alert>
      ) : null}
      {actionError ? (
        <Alert variant="destructive" role="alert">
          {actionError}
        </Alert>
      ) : null}
      {users.isPending ? (
        <p aria-busy="true" className="text-sm text-muted-foreground">
          {labels.admin.users.loading}
        </p>
      ) : users.isError ? (
        <ListError error={users.error} />
      ) : rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">{labels.admin.users.empty}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="px-3 py-2 font-medium">{labels.admin.users.columns.name}</th>
                <th className="px-3 py-2 font-medium">{labels.admin.users.columns.email}</th>
                <th className="px-3 py-2 font-medium">{labels.admin.users.columns.role}</th>
                <th className="px-3 py-2 font-medium">{labels.admin.users.columns.status}</th>
                <th className="px-3 py-2 font-medium">{labels.admin.users.columns.actions}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((user) => (
                <UserRow
                  key={user.id}
                  user={user}
                  isSelf={user.id === me?.id}
                  onNotice={() => setNotice(null)}
                  onActionError={setActionError}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
      {users.hasNextPage ? (
        <div>
          <Button
            variant="outline"
            onClick={() => void users.fetchNextPage()}
            disabled={users.isFetchingNextPage}
          >
            {users.isFetchingNextPage ? labels.admin.users.loading : labels.admin.users.loadMore}
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function ListError({ error }: { error: unknown }) {
  useEffect(() => {
    if (isUnexpectedError(error)) {
      reportError(error, {
        route: "users-table",
        requestId: error instanceof ApiError ? error.requestId : null,
      });
    }
  }, [error]);
  return (
    <Alert variant="destructive" role="alert">
      {apiMessage(error)}
    </Alert>
  );
}

function UserRow({
  user,
  isSelf,
  onNotice,
  onActionError,
}: {
  user: AdminUser;
  isSelf: boolean;
  onNotice: () => void;
  onActionError: (message: string | null) => void;
}) {
  const update = useUpdateUser();
  const pendingRole = update.isPending ? update.variables.body.role : undefined;
  const role: Role = pendingRole ?? user.role;
  const locked = isSelf || update.isPending;
  const hint = isSelf ? labels.admin.users.selfHint : undefined;

  function send(body: { role: Role } | { is_active: boolean }) {
    onNotice();
    onActionError(null);
    update.mutate(
      { id: user.id, body },
      {
        onError: (error) => {
          if (isUnexpectedError(error)) {
            reportError(error, {
              route: "users-table",
              requestId: error instanceof ApiError ? error.requestId : null,
            });
          }
          onActionError(apiMessage(error));
        },
      },
    );
  }

  return (
    <tr data-testid="user-row" className="border-b border-border">
      <td className="px-3 py-2">
        <span>{user.full_name}</span>
        {isSelf ? (
          <span className="ml-2 border border-border px-1.5 py-0.5 text-xs">
            {labels.admin.users.you}
          </span>
        ) : null}
      </td>
      <td className="px-3 py-2">{user.email}</td>
      <td className="px-3 py-2">
        <Select
          aria-label={labels.admin.users.roleFor(user.email)}
          className="h-9 w-36"
          value={role}
          disabled={locked}
          title={hint}
          onChange={(event) => send({ role: event.target.value as Role })}
        >
          <option value="marketer">{labels.admin.users.roles.marketer}</option>
          <option value="admin">{labels.admin.users.roles.admin}</option>
        </Select>
      </td>
      <td className="px-3 py-2">
        <span data-testid="user-status">{labels.admin.users.status[user.status]}</span>
      </td>
      <td className="px-3 py-2">
        <Button
          variant="outline"
          size="sm"
          disabled={locked}
          title={hint}
          onClick={() => send({ is_active: !user.is_active })}
        >
          {user.is_active ? labels.admin.users.deactivate : labels.admin.users.reactivate}
        </Button>
      </td>
    </tr>
  );
}
