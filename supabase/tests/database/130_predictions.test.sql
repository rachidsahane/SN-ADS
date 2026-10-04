-- Demo: predictions (RLS enabled and forced, owner-only policies, grants).
begin;
\ir _helpers.psql
select plan(13);

select tests.deactivate_existing_admins();
select tests.create_user('c2000000-0000-0000-0000-00000000000a', 'p5-admin@x.test', 'Demo Admin', 'admin');
select tests.create_user('c2000000-0000-0000-0000-00000000000b', 'p5-marketer-b@x.test', 'Marketer B');
select tests.create_user('c2000000-0000-0000-0000-00000000000c', 'p5-marketer-c@x.test', 'Marketer C');

-- a model version to point at (status failed: no unique-index conflict with queued/running or active)
insert into public.model_versions (requested_by, status) values ('c2000000-0000-0000-0000-00000000000a', 'failed');

select is((select relrowsecurity and relforcerowsecurity from pg_class where oid = to_regclass('public.predictions')),
  true, 'predictions: RLS enabled and forced');

select tests.authenticate_as('c2000000-0000-0000-0000-00000000000b');
select lives_ok($$insert into public.predictions (user_id, model_version_id, name, inputs, results)
  select 'c2000000-0000-0000-0000-00000000000b', id, 'B first', '{}', '{}' from public.model_versions limit 1$$,
  'predictions (+): a user saves a prediction as themselves');
select throws_ok($$insert into public.predictions (user_id, model_version_id, name, inputs, results)
  select 'c2000000-0000-0000-0000-00000000000c', id, 'Forged', '{}', '{}' from public.model_versions limit 1$$,
  '42501', null, 'predictions (-): a user cannot save a prediction for someone else');
select throws_ok($$insert into public.predictions (user_id, model_version_id, name, inputs, results)
  select 'c2000000-0000-0000-0000-00000000000b', id, '', '{}', '{}' from public.model_versions limit 1$$,
  '23514', null, 'predictions (-): an empty name is refused');
select is((select count(*)::int from public.predictions), 1, 'predictions (+): a user reads their own prediction');
select throws_ok($$update public.predictions set name = 'x'$$, '42501', null,
  'predictions (-): no update is granted (frozen results)');
select tests.reset_role();

select tests.authenticate_as('c2000000-0000-0000-0000-00000000000c');
select is((select count(*)::int from public.predictions), 0, 'predictions (-): another marketer reads nothing');
select is(tests.exec_count($$delete from public.predictions$$)::int, 0,
  'predictions (-): another marketer deletes nothing');
select tests.reset_role();

select tests.authenticate_as('c2000000-0000-0000-0000-00000000000a');
select is((select count(*)::int from public.predictions), 0, 'predictions (-): an administrator does not see others'' predictions');
select is(tests.exec_count($$delete from public.predictions$$)::int, 0,
  'predictions (-): an administrator cannot delete others'' predictions');
select tests.reset_role();

select tests.authenticate_as_anon();
select throws_ok($$select count(*) from public.predictions$$, '42501', null, 'predictions (-): anon has no access');
select tests.reset_role();

select tests.authenticate_as('c2000000-0000-0000-0000-00000000000b');
select is(tests.exec_count($$delete from public.predictions$$)::int, 1, 'predictions (+): the owner deletes their prediction');
select tests.reset_role();

select tests.authenticate_as_service_role();
select throws_ok($$select count(*) from public.predictions$$, '42501', null,
  'predictions (-): the service role has no grant (never needed)');
select tests.reset_role();

select * from finish();
rollback;
