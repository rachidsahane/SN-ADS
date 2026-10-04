-- Demo migration: predictions (DATA_MODEL simplified: the full simulate result is frozen in `results`) - D-922
create table public.predictions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles (id) on delete cascade,
  model_version_id uuid not null references public.model_versions (id) on delete restrict,
  name text not null check (char_length(name) between 1 and 100),
  inputs jsonb not null,
  results jsonb not null,
  created_at timestamptz not null default now()
);
create index predictions_user_created_idx on public.predictions (user_id, created_at desc);

alter table public.predictions enable row level security;
alter table public.predictions force row level security;
revoke all on public.predictions from anon, authenticated, service_role;
grant select, insert, delete on public.predictions to authenticated;
-- Owner only: administrators do NOT see other users' predictions.
create policy predictions_select_own on public.predictions
  for select to authenticated using (user_id = (select auth.uid()) and public.is_active_user());
create policy predictions_insert_own on public.predictions
  for insert to authenticated with check (user_id = (select auth.uid()) and public.is_active_user());
create policy predictions_delete_own on public.predictions
  for delete to authenticated using (user_id = (select auth.uid()) and public.is_active_user());
