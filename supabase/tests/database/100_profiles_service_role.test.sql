-- Phase 2: the service_role privileges on public.profiles (migration 1), used for the first time by
-- app.cli.bootstrap_admin and app.cli.create_test_users (the closed list of ARCHITECTURE 2.5):
--   select on every column, update of full_name, role and is_active ONLY; no insert, no delete,
--   no update of id / email / created_at / updated_at. The service role bypasses RLS, so the
--   LAST_ADMIN guard (trigger, security definer) is the only thing standing between it and an
--   application with zero active admin. No new table in phase 2, so no new RLS policy to test here.
begin;
\ir _helpers.psql
select plan(23);

-- Fixtures independent of existing data: two active admins, one marketer, one extra marketer.
select tests.deactivate_existing_admins();
select tests.create_user('a0000000-0000-0000-0000-000000000001', 'svc-admin1@x.test', 'Svc Admin One', 'admin');
select tests.create_user('a0000000-0000-0000-0000-000000000002', 'svc-admin2@x.test', 'Svc Admin Two', 'admin');
select tests.create_user('a0000000-0000-0000-0000-000000000003', 'svc-market@x.test', 'Svc Market');
select tests.create_user('a0000000-0000-0000-0000-000000000004', 'svc-market2@x.test', 'Svc Market Two');

-- Privileges (catalogue level, independent of any row)
select is(
  (select rolbypassrls from pg_roles where rolname = 'service_role'), true,
  'premise: service_role bypasses RLS (so the column grants and the guard trigger are its only limits)');
select is(
  (select array_agg(c.attname::text order by c.attname::text) from pg_attribute c
    where c.attrelid = 'public.profiles'::regclass and c.attnum > 0 and not c.attisdropped
      and has_column_privilege('service_role', 'public.profiles', c.attname, 'UPDATE')),
  array['full_name', 'is_active', 'role'],
  'grant: service_role may update full_name, is_active and role, and no other column');
select is(has_column_privilege('service_role', 'public.profiles', 'email', 'UPDATE'), false,
  'grant: service_role cannot update email');
select is(has_column_privilege('service_role', 'public.profiles', 'id', 'UPDATE'), false,
  'grant: service_role cannot update id');
select is(has_table_privilege('service_role', 'public.profiles', 'SELECT'), true,
  'grant: service_role can select on profiles');
select is(
  (select count(*)::int from unnest(array['INSERT', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER']) as p
    where has_table_privilege('service_role', 'public.profiles', p)),
  0, 'grant: service_role holds no insert, delete, truncate, references or trigger privilege on profiles');

select tests.authenticate_as_service_role();

-- (+) reads
select is(
  (select email from public.profiles where id = 'a0000000-0000-0000-0000-000000000003'),
  'svc-market@x.test', 'select (+): service_role reads a profile it does not own, without a user claim');
select cmp_ok(
  (select count(*)::int from public.profiles where id::text like 'a0000000-%'), '=', 4,
  'select (+): service_role reads every profile (RLS bypassed)');

-- (+) allowed updates
select lives_ok(
  $$update public.profiles set full_name = 'Svc Market Renamed' where id = 'a0000000-0000-0000-0000-000000000003'$$,
  'update (+): service_role can change full_name');
select is(
  (select full_name from public.profiles where id = 'a0000000-0000-0000-0000-000000000003'),
  'Svc Market Renamed', 'update (+): the full_name change is visible');
select lives_ok(
  $$update public.profiles set role = 'admin' where id = 'a0000000-0000-0000-0000-000000000003'$$,
  'update (+): service_role can promote a marketer to admin (bootstrap_admin)');
select is(
  (select role::text from public.profiles where id = 'a0000000-0000-0000-0000-000000000003'),
  'admin', 'update (+): the promoted profile is now an admin');
select lives_ok(
  $$update public.profiles set is_active = false where id = 'a0000000-0000-0000-0000-000000000004'$$,
  'update (+): service_role can deactivate a marketer');
select is(
  (select is_active from public.profiles where id = 'a0000000-0000-0000-0000-000000000004'),
  false, 'update (+): the deactivated profile is inactive');

-- (-) refused statements
select throws_ok(
  $$update public.profiles set email = 'hijack@x.test' where id = 'a0000000-0000-0000-0000-000000000004'$$,
  '42501', null, 'update (-): service_role cannot change an e-mail');
select throws_ok(
  $$insert into public.profiles (id, email, full_name) values ('a0000000-0000-0000-0000-0000000000ff', 'ghost@x.test', 'Ghost')$$,
  '42501', null, 'insert (-): service_role cannot insert a profile (profiles are born from auth.users only)');
select throws_ok(
  $$delete from public.profiles where id = 'a0000000-0000-0000-0000-000000000004'$$,
  '42501', null, 'delete (-): service_role cannot delete a profile');

-- Guard LAST_ADMIN applies to the bypassrls role. Admins now: 1, 2 and 3 (promoted above). Reduce to one.
select lives_ok(
  $$update public.profiles set role = 'marketer' where id in ('a0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000003')$$,
  'guard (+): with three active admins, two can be demoted');
select throws_ok(
  $$update public.profiles set role = 'marketer' where id = 'a0000000-0000-0000-0000-000000000001'$$,
  'P0001', 'LAST_ADMIN', 'guard (-): service_role cannot demote the last active admin');
select throws_ok(
  $$update public.profiles set is_active = false where id = 'a0000000-0000-0000-0000-000000000001'$$,
  'P0001', 'LAST_ADMIN', 'guard (-): service_role cannot deactivate the last active admin');
select lives_ok(
  $$update public.profiles set role = 'admin' where id = 'a0000000-0000-0000-0000-000000000002'$$,
  'guard (+): promoting another profile to admin is allowed');
select lives_ok(
  $$update public.profiles set role = 'marketer' where id = 'a0000000-0000-0000-0000-000000000001'$$,
  'guard (+): with a second active admin in place, the former last admin can be demoted');

select tests.reset_role();
select is(
  (select array_agg(id::text order by id::text) from public.profiles
    where role = 'admin' and is_active and id::text like 'a0000000-%'),
  array['a0000000-0000-0000-0000-000000000002'],
  'after the sequence exactly one of our admins is active, the guard never let it reach zero');

select * from finish();
rollback;
