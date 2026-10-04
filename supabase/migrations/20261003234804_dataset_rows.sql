-- Demo migration: dataset_rows (DATA_MODEL 4.3, simplified: no upload_id, no dataset_uploads) - D-demo
create table public.dataset_rows (
  id uuid primary key default gen_random_uuid(),
  source public.dataset_source not null,
  external_id bigint not null check (external_id >= 1),
  is_holdout boolean not null,
  age smallint not null check (age between 18 and 100),
  gender public.gender not null,
  income integer not null check (income between 0 and 100000000),
  campaign_channel public.campaign_channel not null,
  campaign_type public.campaign_type not null,
  ad_spend double precision not null check (ad_spend > 0 and ad_spend <= 10000000),
  click_through_rate double precision not null check (click_through_rate between 0 and 1),
  conversion_rate double precision not null check (conversion_rate between 0 and 1),
  website_visits integer not null check (website_visits between 0 and 100000000),
  pages_per_visit double precision not null check (pages_per_visit between 0 and 1000),
  time_on_site double precision not null check (time_on_site between 0 and 1440),
  social_shares integer not null check (social_shares between 0 and 10000000),
  email_opens integer not null check (email_opens between 0 and 10000000),
  email_clicks integer not null check (email_clicks between 0 and 10000000),
  previous_purchases integer not null check (previous_purchases between 0 and 10000),
  loyalty_points integer not null check (loyalty_points between 0 and 10000000),
  advertising_platform text not null check (char_length(advertising_platform) between 1 and 100),
  advertising_tool text not null check (char_length(advertising_tool) between 1 and 100),
  conversion smallint not null check (conversion in (0, 1)),
  created_at timestamptz not null default now()
);
create unique index dataset_rows_source_external_unique on public.dataset_rows (source, external_id);
create index dataset_rows_scope_idx on public.dataset_rows (source, is_holdout);
create index dataset_rows_type_idx on public.dataset_rows (campaign_type);

alter table public.dataset_rows enable row level security;
alter table public.dataset_rows force row level security;
revoke all on public.dataset_rows from anon, authenticated, service_role;
grant select on public.dataset_rows to authenticated;          -- administrators only (policy below)
grant select, insert on public.dataset_rows to service_role;   -- seed command and training job
create policy dataset_rows_select_admin on public.dataset_rows
  for select to authenticated using (public.is_admin());
