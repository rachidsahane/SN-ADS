-- Demo migration: model_versions (DATA_MODEL 4.4, simplified: no comparison, no is_activatable) - D-demo
create table public.model_versions (
  id uuid primary key default gen_random_uuid(),
  version bigint generated always as identity unique,
  status public.training_status not null default 'queued',
  data_scope public.data_scope not null default 'all' check (data_scope = 'all'),
  requested_by uuid references public.profiles (id),
  metrics jsonb,
  global_importance jsonb,
  features_used text[],
  train_row_count integer,
  holdout_row_count integer,
  error_message text,
  is_active boolean not null default false,
  activated_at timestamptz,
  activated_by uuid references public.profiles (id),
  artifact_prefix text,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz,
  check (not is_active or status = 'succeeded')
);
create unique index model_versions_one_active on public.model_versions ((true)) where is_active;
create unique index model_versions_one_in_progress on public.model_versions ((true))
  where status in ('queued', 'running');
create index model_versions_created_idx on public.model_versions (created_at desc);

alter table public.model_versions enable row level security;
alter table public.model_versions force row level security;
revoke all on public.model_versions from anon, authenticated, service_role;
grant select on public.model_versions to authenticated;
grant insert on public.model_versions to authenticated;        -- administrators only (policy below)
grant select, insert, update on public.model_versions to service_role;  -- training job, start-up cleanup
create policy model_versions_select_active_user on public.model_versions
  for select to authenticated using (public.is_active_user());
create policy model_versions_insert_admin on public.model_versions
  for insert to authenticated
  with check (public.is_admin() and requested_by = (select auth.uid()) and status = 'queued');

-- Activation: one atomic switch (the previous active version is deactivated in the same statement).
create or replace function public.activate_model_version(p_id uuid)
returns public.model_versions
language plpgsql security definer set search_path = '' as $$
declare
  v public.model_versions;
begin
  if not public.is_admin() then
    raise exception 'FORBIDDEN' using errcode = 'P0001';
  end if;
  select * into v from public.model_versions where id = p_id for update;
  if not found then
    raise exception 'NOT_FOUND' using errcode = 'P0001';
  end if;
  if v.status <> 'succeeded' then
    raise exception 'MODEL_NOT_ACTIVATABLE' using errcode = 'P0001';
  end if;
  update public.model_versions set is_active = false where is_active and id <> p_id;
  update public.model_versions
     set is_active = true, activated_at = now(), activated_by = (select auth.uid())
   where id = p_id
  returning * into v;
  return v;
end $$;
revoke all on function public.activate_model_version(uuid) from public, anon, authenticated, service_role;
grant execute on function public.activate_model_version(uuid) to authenticated;
