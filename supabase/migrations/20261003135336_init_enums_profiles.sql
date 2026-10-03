-- Phase 1, migration 1: enumerated types, profiles, access helper functions, triggers, RLS (DATA_MODEL 3, 4.1, 5, 6)

-- 0. Hardening. The Supabase image grants ALL on new public tables, sequences and functions to anon,
--    authenticated and service_role by default, and PostgreSQL lets PUBLIC execute new functions.
--    DATA_MODEL 6 requires "no right for anon" and SECURITY_NOTES 3.7 requires execute for authenticated only,
--    so remove every default first: each object then receives explicit grants in its own migration.
alter default privileges in schema public revoke all on tables from anon, authenticated, service_role;
alter default privileges in schema public revoke all on sequences from anon, authenticated, service_role;
alter default privileges in schema public revoke all on functions from anon, authenticated, service_role;
-- (not schema-scoped: the implicit "execute for PUBLIC" default can only be removed globally)
alter default privileges revoke execute on functions from public;
revoke all on all tables in schema public from anon, authenticated, service_role;
revoke all on all sequences in schema public from anon, authenticated, service_role;
revoke all on all functions in schema public from public, anon, authenticated, service_role;

-- 1. Types (verbatim DATA_MODEL 3)
create type public.app_role as enum ('marketer', 'admin');
create type public.gender as enum ('Male', 'Female');
create type public.campaign_channel as enum ('Social Media', 'Email', 'PPC', 'SEO', 'Referral');
create type public.campaign_type as enum ('Awareness', 'Consideration', 'Conversion', 'Retention');
create type public.dataset_source as enum ('seed', 'agency');
create type public.upload_status as enum ('importing', 'ready', 'failed');
create type public.training_status as enum ('queued', 'running', 'succeeded', 'failed');
create type public.data_scope as enum ('all', 'agency_only');
create type public.performance_level as enum ('low', 'medium', 'high');

-- 2. profiles (DATA_MODEL 4.1)
create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  email text not null unique,
  full_name text not null check (char_length(full_name) between 1 and 120),
  role public.app_role not null default 'marketer',
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index profiles_role_active_idx on public.profiles (role, is_active);

-- 3. Helper functions (verbatim DATA_MODEL 5) + privileges (SECURITY_NOTES 3.7)
create or replace function public.is_active_user() returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (
    select 1 from public.profiles p
    where p.id = (select auth.uid()) and p.is_active
  );
$$;
create or replace function public.is_admin() returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (
    select 1 from public.profiles p
    where p.id = (select auth.uid()) and p.role = 'admin' and p.is_active
  );
$$;
revoke all on function public.is_active_user() from public, anon, authenticated, service_role;
revoke all on function public.is_admin() from public, anon, authenticated, service_role;
grant execute on function public.is_active_user() to authenticated;
grant execute on function public.is_admin() to authenticated;

-- 4. Triggers
create or replace function public.set_updated_at() returns trigger
language plpgsql set search_path = '' as $$
begin
  new.updated_at = now();
  return new;
end $$;
revoke all on function public.set_updated_at() from public, anon, authenticated, service_role;
create trigger profiles_set_updated_at before update on public.profiles
  for each row execute function public.set_updated_at();

-- DATA_MODEL 4.1: the role is NEVER read from user metadata (SEC-04). Hardened name rule: a blank or
-- >120-character full_name must not abort user creation (profiles.full_name check 1..120). "Blank" covers
-- invisible whitespace too (tab, newline, no-break space, zero-width space, BOM): btrim() alone strips spaces only.
create or replace function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into public.profiles (id, email, full_name)
  values (
    new.id,
    new.email,
    coalesce(
      nullif(left(btrim(new.raw_user_meta_data ->> 'full_name', E' \t\r\n\f\u000b\u00a0\u200b\ufeff'), 120), ''),
      nullif(left(split_part(new.email, '@', 1), 120), ''),
      'User'
    )
  );
  return new;
end $$;
revoke all on function public.handle_new_user() from public, anon, authenticated, service_role;
create trigger on_auth_user_created after insert on auth.users
  for each row execute function public.handle_new_user();

create or replace function public.guard_last_admin() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  perform pg_advisory_xact_lock(hashtext('profiles_admin_guard'));
  if old.role = 'admin' and old.is_active and not (new.role = 'admin' and new.is_active) then
    if not exists (
      select 1 from public.profiles p where p.id <> old.id and p.role = 'admin' and p.is_active
    ) then
      raise exception 'LAST_ADMIN' using errcode = 'P0001';
    end if;
  end if;
  return new;
end $$;
revoke all on function public.guard_last_admin() from public, anon, authenticated, service_role;
create trigger profiles_guard_last_admin before update on public.profiles
  for each row execute function public.guard_last_admin();

-- 5. RLS (DATA_MODEL 6: forced, per-column update rights, no insert/delete for anyone through the API)
alter table public.profiles enable row level security;
alter table public.profiles force row level security;
revoke all on public.profiles from anon, authenticated;
grant select on public.profiles to authenticated;
grant update (full_name, role, is_active) on public.profiles to authenticated;
-- Server side (service key, closed list of modules: user admin, bootstrap, CLI): read profiles and change the same three
-- columns. No insert (the auth.users trigger creates profiles) and no delete (removal goes through auth.users cascade).
revoke all on public.profiles from service_role;
grant select on public.profiles to service_role;
grant update (full_name, role, is_active) on public.profiles to service_role;
create policy profiles_select_own_or_admin on public.profiles
  for select to authenticated
  using (((id = (select auth.uid())) and public.is_active_user()) or public.is_admin());
create policy profiles_update_by_admin on public.profiles
  for update to authenticated
  using (public.is_admin() and id <> (select auth.uid()))
  with check (public.is_admin() and id <> (select auth.uid()));

-- 6. Readiness probe helper (decision D-049): the ONLY function callable by anon; it returns nothing but the
--    last applied migration identifier, which /api/ready publishes anyway. Written in plpgsql on purpose: a
--    "language sql" body would be validated at creation, when supabase_migrations.schema_migrations may not
--    exist yet.
create or replace function public.schema_version() returns text
language plpgsql stable security definer set search_path = '' as $$
declare v text;
begin
  select max(version) into v from supabase_migrations.schema_migrations;
  return coalesce(v, '');
end $$;
revoke all on function public.schema_version() from public, anon, authenticated, service_role;
grant execute on function public.schema_version() to anon, authenticated;
