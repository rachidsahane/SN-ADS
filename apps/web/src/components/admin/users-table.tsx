"use client";

import { useEffect, useState } from "react";

import { InviteUserDialog } from "@/components/admin/invite-user-dialog";
import { PageTitle } from "@/components/layout/page-title";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tag } from "@/components/ui/tag";
import { type AdminUser, useAdminUsers, useUpdateUser } from "@/hooks/use-admin-users";
import { useMe } from "@/hooks/use-me";
import { ApiError } from "@/lib/api/client";
import { apiMessage, isUnexpectedError } from "@/lib/api/messages";
import { labels } from "@/lib/labels";
import { reportError } from "@/lib/observability";
import { useToast } from "@/providers/toast-provider";

type Role = AdminUser["role"];
const STATUS_TONE = { active: "accent", invited: "outline", deactivated: "neutral" } as const;

/** Tableau des utilisateurs (PRD US-03, US-04) : rôle, activation, invitation. Tout texte venu des données est affiché comme texte. */
export function UsersTable() {
  const { data: me } = useMe();
  const users = useAdminUsers();
  const { toast } = useToast();
  const [inviteOpen, setInviteOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const rows = users.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <>
      <PageTitle
        subtitle={labels.admin.users.subtitle}
        actions={
          <Button blueprint onClick={() => setInviteOpen(true)}>
            {labels.admin.users.invite}
          </Button>
        }
      >
        {labels.admin.users.title}
      </PageTitle>
      <InviteUserDialog
        open={inviteOpen}
        onClose={() => setInviteOpen(false)}
        onInvited={(email) => {
          setActionError(null);
          toast(labels.admin.users.invitedNotice(email));
        }}
      />
      {actionError ? (
        <Alert variant="destructive" role="alert">
          {actionError}
        </Alert>
      ) : null}
      {users.isPending ? (
        <div aria-busy="true" className="flex flex-col gap-1">
          <Skeleton className="h-8" />
          {[0, 1, 2, 3].map((row) => (
            <Skeleton key={row} className="h-11 opacity-70" />
          ))}
        </div>
      ) : users.isError ? (
        <ListError error={users.error} />
      ) : rows.length === 0 ? (
        <div className="blueprint p-10 text-center text-neutral-700">
          {labels.admin.users.empty}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="table">
            <thead>
              <tr>
                <th>{labels.admin.users.columns.name}</th>
                <th>{labels.admin.users.columns.email}</th>
                <th>{labels.admin.users.columns.role}</th>
                <th>{labels.admin.users.columns.status}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((user) => (
                <UserRow
                  key={user.id}
                  user={user}
                  isSelf={user.id === me?.id}
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
    </>
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
  onActionError,
}: {
  user: AdminUser;
  isSelf: boolean;
  onActionError: (message: string | null) => void;
}) {
  const update = useUpdateUser();
  const pendingRole = update.isPending ? update.variables.body.role : undefined;
  const role: Role = pendingRole ?? user.role;
  const locked = isSelf || update.isPending;
  const hint = isSelf ? labels.admin.users.selfHint : undefined;

  function send(body: { role: Role } | { is_active: boolean }) {
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
    <tr data-testid="user-row">
      <td>
        <span>{user.full_name}</span>
        {isSelf ? (
          <span className="text-xs text-neutral-700"> {labels.admin.users.you}</span>
        ) : null}
      </td>
      <td>{user.email}</td>
      <td>
        <Select
          aria-label={labels.admin.users.roleFor(user.email)}
          className="!min-h-[30px] !w-auto !px-2 !py-[3px]"
          value={role}
          disabled={locked}
          title={hint}
          onChange={(event) => send({ role: event.target.value as Role })}
        >
          <option value="marketer">{labels.admin.users.roles.marketer}</option>
          <option value="admin">{labels.admin.users.roles.admin}</option>
        </Select>
      </td>
      <td>
        <Tag tone={STATUS_TONE[user.status]} data-testid="user-status">
          {labels.admin.users.status[user.status]}
        </Tag>
      </td>
      <td className="text-right">
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
