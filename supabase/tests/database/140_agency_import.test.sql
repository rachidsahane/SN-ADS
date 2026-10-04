-- Demo: real import of agency data (admin INSERT policy on dataset_rows, source 'agency' only; scope 'agency_only').
begin;
\ir _helpers.psql
select plan(14);

select tests.deactivate_existing_admins();
select tests.create_user('c3000000-0000-0000-0000-00000000000a', 'p6-admin@x.test', 'Import Admin', 'admin');
select tests.create_user('c3000000-0000-0000-0000-00000000000b', 'p6-marketer@x.test', 'Import Marketer');
select tests.create_user('c3000000-0000-0000-0000-00000000000c', 'p6-off-admin@x.test', 'Off Admin', 'admin', false);

-- Start from a clean slate inside this transaction (the local database may hold real rows).
delete from public.model_versions;
delete from public.dataset_rows where external_id between 900000101 and 900000110;

select is((select relrowsecurity and relforcerowsecurity from pg_class where oid = to_regclass('public.dataset_rows')),
  true, 'dataset_rows: RLS still enabled and forced');

select tests.authenticate_as('c3000000-0000-0000-0000-00000000000a');
select lives_ok($$insert into public.dataset_rows (source, external_id, is_holdout, age, gender, income, campaign_channel,
    campaign_type, ad_spend, click_through_rate, conversion_rate, website_visits, pages_per_visit, time_on_site,
    social_shares, email_opens, email_clicks, previous_purchases, loyalty_points, advertising_platform,
    advertising_tool, conversion)
  values ('agency', 900000101, false, 30, 'Female', 1000, 'Email', 'Awareness', 100, 0.1, 0.1, 10, 2, 3, 1, 1, 1, 1, 1, 'p', 't', 1)$$,
  'dataset_rows (+): an administrator inserts an agency row with their own token');
select throws_ok($$insert into public.dataset_rows (source, external_id, is_holdout, age, gender, income, campaign_channel,
    campaign_type, ad_spend, click_through_rate, conversion_rate, website_visits, pages_per_visit, time_on_site,
    social_shares, email_opens, email_clicks, previous_purchases, loyalty_points, advertising_platform,
    advertising_tool, conversion)
  values ('seed', 900000102, false, 30, 'Female', 1000, 'Email', 'Awareness', 100, 0.1, 0.1, 10, 2, 3, 1, 1, 1, 1, 1, 'p', 't', 1)$$,
  '42501', null, 'dataset_rows (-): an administrator cannot insert a seed row');
select throws_ok($$insert into public.dataset_rows (source, external_id, is_holdout, age, gender, income, campaign_channel,
    campaign_type, ad_spend, click_through_rate, conversion_rate, website_visits, pages_per_visit, time_on_site,
    social_shares, email_opens, email_clicks, previous_purchases, loyalty_points, advertising_platform,
    advertising_tool, conversion)
  values ('agency', 900000101, false, 30, 'Female', 1000, 'Email', 'Awareness', 100, 0.1, 0.1, 10, 2, 3, 1, 1, 1, 1, 1, 'p', 't', 1)$$,
  '23505', null, 'dataset_rows (-): the same agency id cannot be imported twice');
select throws_ok($$insert into public.dataset_rows (source, external_id, is_holdout, age, gender, income, campaign_channel,
    campaign_type, ad_spend, click_through_rate, conversion_rate, website_visits, pages_per_visit, time_on_site,
    social_shares, email_opens, email_clicks, previous_purchases, loyalty_points, advertising_platform,
    advertising_tool, conversion)
  values ('agency', 900000103, false, 10, 'Female', 1000, 'Email', 'Awareness', 100, 0.1, 0.1, 10, 2, 3, 1, 1, 1, 1, 1, 'p', 't', 1)$$,
  '23514', null, 'dataset_rows (-): the table constraints still apply to an import');
select is((select count(*)::int from public.dataset_rows where external_id = 900000101 and source = 'agency'), 1,
  'dataset_rows (+): the administrator reads the imported row');
select throws_ok($$update public.dataset_rows set age = 40 where external_id = 900000101$$, '42501', null,
  'dataset_rows (-): an administrator cannot update an imported row');
select throws_ok($$delete from public.dataset_rows where external_id = 900000101$$, '42501', null,
  'dataset_rows (-): an administrator cannot delete an imported row');
select lives_ok($$insert into public.model_versions (requested_by, data_scope)
  values ('c3000000-0000-0000-0000-00000000000a', 'agency_only')$$,
  'model_versions (+): an administrator requests an "agency_only" training');
select tests.reset_role();

select tests.authenticate_as('c3000000-0000-0000-0000-00000000000b');
select throws_ok($$insert into public.dataset_rows (source, external_id, is_holdout, age, gender, income, campaign_channel,
    campaign_type, ad_spend, click_through_rate, conversion_rate, website_visits, pages_per_visit, time_on_site,
    social_shares, email_opens, email_clicks, previous_purchases, loyalty_points, advertising_platform,
    advertising_tool, conversion)
  values ('agency', 900000104, false, 30, 'Female', 1000, 'Email', 'Awareness', 100, 0.1, 0.1, 10, 2, 3, 1, 1, 1, 1, 1, 'p', 't', 1)$$,
  '42501', null, 'dataset_rows (-): a marketer cannot insert an agency row');
select is((select count(*)::int from public.dataset_rows), 0, 'dataset_rows (-): a marketer still reads nothing');
select tests.reset_role();

select tests.authenticate_as('c3000000-0000-0000-0000-00000000000c');
select throws_ok($$insert into public.dataset_rows (source, external_id, is_holdout, age, gender, income, campaign_channel,
    campaign_type, ad_spend, click_through_rate, conversion_rate, website_visits, pages_per_visit, time_on_site,
    social_shares, email_opens, email_clicks, previous_purchases, loyalty_points, advertising_platform,
    advertising_tool, conversion)
  values ('agency', 900000105, false, 30, 'Female', 1000, 'Email', 'Awareness', 100, 0.1, 0.1, 10, 2, 3, 1, 1, 1, 1, 1, 'p', 't', 1)$$,
  '42501', null, 'dataset_rows (-): a deactivated administrator cannot insert an agency row');
select tests.reset_role();

select tests.authenticate_as_anon();
select throws_ok($$insert into public.dataset_rows (source, external_id) values ('agency', 900000106)$$, '42501', null,
  'dataset_rows (-): anon cannot insert');
select tests.reset_role();

select throws_ok($$insert into public.model_versions (data_scope) values ('everything')$$,
  '22P02', null, 'model_versions (-): an unknown scope is refused');

select * from finish();
rollback;
