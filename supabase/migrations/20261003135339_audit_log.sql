-- Phase 1, migration 2: append-only audit_log and log_audit() (DATA_MODEL 4.6, 5, 6)
create table public.audit_log (
  id bigint generated always as identity primary key,
  actor_id uuid references public.profiles (id) on delete set null,
  action text not null check (action in (
    'user.invited', 'user.role_changed', 'user.deactivated', 'user.reactivated',
    'upload.accepted', 'upload.failed',
    'model.training_requested', 'model.training_succeeded', 'model.training_failed',
    'model.activated')),
  target_type text not null check (target_type in ('user', 'upload', 'model_version')),
  target_id text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index audit_log_created_idx on public.audit_log (created_at desc, id desc);

alter table public.audit_log enable row level security;
alter table public.audit_log force row level security;
-- append-only: no update/delete/truncate for anyone except the owner postgres
revoke all on public.audit_log from anon, authenticated, service_role;
grant select on public.audit_log to authenticated;
grant insert on public.audit_log to service_role;            -- worker and app.cli.* (service key)
create policy audit_log_select_admin on public.audit_log
  for select to authenticated using (public.is_admin());

create or replace function public.log_audit(
  p_action text, p_target_type text, p_target_id text, p_metadata jsonb
) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if not public.is_admin() then
    raise exception 'FORBIDDEN' using errcode = 'P0001';
  end if;
  insert into public.audit_log (actor_id, action, target_type, target_id, metadata)
  values ((select auth.uid()), p_action, p_target_type, p_target_id, coalesce(p_metadata, '{}'::jsonb));
end $$;
revoke all on function public.log_audit(text, text, text, jsonb) from public, anon, authenticated, service_role;
grant execute on function public.log_audit(text, text, text, jsonb) to authenticated;
