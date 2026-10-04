-- Demo: dataset_rows and model_versions (RLS enabled and forced, policies, grants, unique indexes, activation).
begin;
\ir _helpers.psql
select plan(26);

select tests.deactivate_existing_admins();
select tests.create_user('c1000000-0000-0000-0000-00000000000a', 'p4-admin@x.test', 'Demo Admin', 'admin');
select tests.create_user('c1000000-0000-0000-0000-00000000000b', 'p4-marketer@x.test', 'Demo Marketer');
select tests.create_user('c1000000-0000-0000-0000-00000000000c', 'p4-off@x.test', 'Demo Inactive', 'marketer', false);

-- Start from a clean slate inside this transaction (the local database may hold real rows).
delete from public.model_versions;
delete from public.dataset_rows where external_id in (900000001, 900000002);

select is((select relrowsecurity and relforcerowsecurity from pg_class where oid = to_regclass('public.dataset_rows')),
  true, 'dataset_rows: RLS enabled and forced');
select is((select relrowsecurity and relforcerowsecurity from pg_class where oid = to_regclass('public.model_versions')),
  true, 'model_versions: RLS enabled and forced');

-- dataset_rows: written by the service role only, read by administrators only
select tests.authenticate_as_service_role();
select lives_ok($$insert into public.dataset_rows (source, external_id, is_holdout, age, gender, income, campaign_channel,
    campaign_type, ad_spend, click_through_rate, conversion_rate, website_visits, pages_per_visit, time_on_site,
    social_shares, email_opens, email_clicks, previous_purchases, loyalty_points, advertising_platform,
    advertising_tool, conversion)
  values ('seed', 900000001, false, 30, 'Female', 1000, 'Email', 'Awareness', 100, 0.1, 0.1, 10, 2, 3, 1, 1, 1, 1, 1, 'p', 't', 1)$$,
  'dataset_rows (+): the service role inserts a row');
select throws_ok($$insert into public.dataset_rows (source, external_id, is_holdout, age, gender, income, campaign_channel,
    campaign_type, ad_spend, click_through_rate, conversion_rate, website_visits, pages_per_visit, time_on_site,
    social_shares, email_opens, email_clicks, previous_purchases, loyalty_points, advertising_platform,
    advertising_tool, conversion)
  values ('seed', 900000001, false, 30, 'Female', 1000, 'Email', 'Awareness', 100, 0.1, 0.1, 10, 2, 3, 1, 1, 1, 1, 1, 'p', 't', 1)$$,
  '23505', null, 'dataset_rows (-): (source, external_id) is unique');
select throws_ok($$insert into public.dataset_rows (source, external_id, is_holdout, age, gender, income, campaign_channel,
    campaign_type, ad_spend, click_through_rate, conversion_rate, website_visits, pages_per_visit, time_on_site,
    social_shares, email_opens, email_clicks, previous_purchases, loyalty_points, advertising_platform,
    advertising_tool, conversion)
  values ('seed', 900000002, false, 10, 'Female', 1000, 'Email', 'Awareness', 100, 0.1, 0.1, 10, 2, 3, 1, 1, 1, 1, 1, 'p', 't', 1)$$,
  '23514', null, 'dataset_rows (-): an age below 18 is refused');
select tests.reset_role();

select tests.authenticate_as('c1000000-0000-0000-0000-00000000000a');
select cmp_ok((select count(*)::int from public.dataset_rows where external_id = 900000001), '=', 1,
  'dataset_rows (+): an administrator reads the rows');
select throws_ok($$delete from public.dataset_rows$$, '42501', null, 'dataset_rows (-): an administrator cannot delete');
select throws_ok($$insert into public.dataset_rows (source, external_id) values ('seed', 900000002)$$, '42501', null,
  'dataset_rows (-): an administrator cannot insert (service role only)');
select tests.reset_role();

select tests.authenticate_as('c1000000-0000-0000-0000-00000000000b');
select is((select count(*)::int from public.dataset_rows), 0, 'dataset_rows (-): a marketer reads nothing');
select tests.reset_role();

select tests.authenticate_as_anon();
select throws_ok($$select count(*) from public.dataset_rows$$, '42501', null, 'dataset_rows (-): anon has no access');
select tests.reset_role();

-- model_versions: an administrator requests a version (insert with check), the service role updates it
select tests.authenticate_as('c1000000-0000-0000-0000-00000000000a');
select lives_ok($$insert into public.model_versions (requested_by) values ('c1000000-0000-0000-0000-00000000000a')$$,
  'model_versions (+): an administrator queues a version as themselves');
select throws_ok($$insert into public.model_versions (requested_by) values ('c1000000-0000-0000-0000-00000000000a')$$,
  '23505', null, 'model_versions (-): only one version can be queued or running');
select throws_ok($$insert into public.model_versions (requested_by, status) values ('c1000000-0000-0000-0000-00000000000b', 'failed')$$,
  '42501', null, 'model_versions (-): requested_by must be the caller and the status queued');
select throws_ok($$update public.model_versions set status = 'succeeded'$$, '42501', null,
  'model_versions (-): an administrator cannot update directly');
select tests.reset_role();

select tests.authenticate_as('c1000000-0000-0000-0000-00000000000b');
select throws_ok($$insert into public.model_versions (requested_by) values ('c1000000-0000-0000-0000-00000000000b')$$,
  '42501', null, 'model_versions (-): a marketer cannot request a training');
select is((select count(*)::int from public.model_versions), 1, 'model_versions (+): an active marketer reads the versions');
select tests.reset_role();

select tests.authenticate_as('c1000000-0000-0000-0000-00000000000c');
select is((select count(*)::int from public.model_versions), 0, 'model_versions (-): an inactive user reads nothing');
select tests.reset_role();

select tests.authenticate_as_service_role();
select lives_ok($$update public.model_versions set status = 'succeeded', finished_at = now()$$,
  'model_versions (+): the service role updates the status');
select lives_ok($$insert into public.model_versions (status) values ('succeeded')$$,
  'model_versions (+): the service role inserts a second finished version');
select tests.reset_role();

-- activation
select tests.authenticate_as('c1000000-0000-0000-0000-00000000000b');
select throws_ok($$select public.activate_model_version((select id from public.model_versions limit 1))$$,
  'P0001', 'FORBIDDEN', 'activate (-): a marketer cannot activate');
select tests.reset_role();

select tests.authenticate_as('c1000000-0000-0000-0000-00000000000a');
select is((public.activate_model_version((select id from public.model_versions order by version limit 1))).is_active, true,
  'activate (+): an administrator activates a succeeded version');
select is((public.activate_model_version((select id from public.model_versions order by version desc limit 1))).is_active, true,
  'activate (+): activating another version switches the active one');
select is((select count(*)::int from public.model_versions where is_active), 1, 'activate: exactly one version is active');
select throws_ok($$select public.activate_model_version(gen_random_uuid())$$, 'P0001', 'NOT_FOUND', 'activate (-): unknown id');
select tests.reset_role();

select tests.authenticate_as_service_role();
select lives_ok($$insert into public.model_versions (status) values ('failed')$$, 'a failed version can be added');
select tests.reset_role();
select tests.authenticate_as('c1000000-0000-0000-0000-00000000000a');
select throws_ok($$select public.activate_model_version((select id from public.model_versions where status = 'failed'))$$,
  'P0001', 'MODEL_NOT_ACTIVATABLE', 'activate (-): a failed version cannot be activated');
select tests.reset_role();

select * from finish();
rollback;
