-- Demo migration: real import of agency data (D-932, lifts D-910 for the import).
-- Administrators may add rows to dataset_rows with their own token, only with source 'agency'
-- (no update, no delete: an import is never edited). Seed rows stay written by the service role only.
grant insert on public.dataset_rows to authenticated;
create policy dataset_rows_insert_admin_agency on public.dataset_rows
  for insert to authenticated
  with check (public.is_admin() and source = 'agency');

-- "Agency data only" training (DATA_MODEL 4.4): the scope may now be 'agency_only'.
alter table public.model_versions drop constraint model_versions_data_scope_check;
alter table public.model_versions
  add constraint model_versions_data_scope_check check (data_scope in ('all', 'agency_only'));
