-- Migration 1: profiles_guard_last_admin (DATA_MODEL 4.1) and profiles_set_updated_at.
-- The guard refuses any change that would leave zero ACTIVE admin (P0001 / LAST_ADMIN).
-- Real concurrency (two sessions racing) cannot be played inside one pgTAP transaction: it is covered by
-- E2E-CONC-06 in phase 3. Here we prove the serialising lock is taken, by reading the function source.
begin;
\ir _helpers.psql
select plan(22);

-- Fixtures independent of existing data: no other active admin, exactly one of ours.
select tests.deactivate_existing_admins();
select tests.create_user('30000000-0000-0000-0000-000000000001', 'admin1@x.test', 'Admin One', 'admin');
select tests.create_user('30000000-0000-0000-0000-000000000002', 'market1@x.test', 'Market One');

select is(
  (select count(*)::int from public.profiles where role = 'admin' and is_active),
  1, 'precondition: exactly one active admin');

-- One active admin: demotion and deactivation are refused
select throws_ok(
  $$update public.profiles set role = 'marketer' where id = '30000000-0000-0000-0000-000000000001'$$,
  'P0001', 'LAST_ADMIN', 'the only active admin cannot be demoted');
select throws_ok(
  $$update public.profiles set is_active = false where id = '30000000-0000-0000-0000-000000000001'$$,
  'P0001', 'LAST_ADMIN', 'the only active admin cannot be deactivated');
select throws_ok(
  $$update public.profiles set role = 'marketer', is_active = false where id = '30000000-0000-0000-0000-000000000001'$$,
  'P0001', 'LAST_ADMIN', 'the only active admin cannot be demoted and deactivated at once');
select is(
  (select role::text from public.profiles where id = '30000000-0000-0000-0000-000000000001'),
  'admin', 'the refused updates changed nothing');

-- Other changes stay possible
select lives_ok(
  $$update public.profiles set full_name = 'Admin Renamed' where id = '30000000-0000-0000-0000-000000000001'$$,
  'the only active admin can still change another column (full_name)');
select is(
  (select full_name from public.profiles where id = '30000000-0000-0000-0000-000000000001'),
  'Admin Renamed', 'the full_name change was applied');
select lives_ok(
  $$update public.profiles set full_name = 'Market Renamed', is_active = false where id = '30000000-0000-0000-0000-000000000002'$$,
  'a marketer can be modified and deactivated whatever the number of admins');

-- Promotion is allowed; with two active admins one of them can be demoted, then the other is the last one
select lives_ok(
  $$update public.profiles set role = 'admin', is_active = true where id = '30000000-0000-0000-0000-000000000002'$$,
  'promoting a marketer to admin is allowed');
select lives_ok(
  $$update public.profiles set role = 'marketer' where id = '30000000-0000-0000-0000-000000000001'$$,
  'with two active admins, one can be demoted');
select throws_ok(
  $$update public.profiles set role = 'marketer' where id = '30000000-0000-0000-0000-000000000002'$$,
  'P0001', 'LAST_ADMIN', 'the remaining admin is now the last one and cannot be demoted');
select throws_ok(
  $$update public.profiles set is_active = false where id = '30000000-0000-0000-0000-000000000002'$$,
  'P0001', 'LAST_ADMIN', 'the remaining admin cannot be deactivated either');

-- An inactive admin does not count as an admin
select tests.create_user('30000000-0000-0000-0000-000000000003', 'admin3@x.test', 'Admin Three', 'admin', false);
select is(
  (select count(*)::int from public.profiles where role = 'admin' and is_active),
  1, 'an inactive admin is not counted as an active admin');
select throws_ok(
  $$update public.profiles set role = 'marketer' where id = '30000000-0000-0000-0000-000000000002'$$,
  'P0001', 'LAST_ADMIN', 'an inactive admin does not save the last active admin');

-- Reactivating an admin is not a reduction: allowed, and it frees the other one
select lives_ok(
  $$update public.profiles set is_active = true where id = '30000000-0000-0000-0000-000000000003'$$,
  'reactivating an inactive admin is allowed');
select lives_ok(
  $$update public.profiles set is_active = false where id = '30000000-0000-0000-0000-000000000002'$$,
  'with another active admin back, the previous one can be deactivated');
select throws_ok(
  $$update public.profiles set role = 'marketer' where id = '30000000-0000-0000-0000-000000000003'$$,
  'P0001', 'LAST_ADMIN', 'and the reactivated admin is now the last one');

-- The lock that serialises concurrent changes is taken by the function itself
select matches(
  (select prosrc from pg_proc where oid = to_regprocedure('public.guard_last_admin()')),
  'pg_advisory_xact_lock\(hashtext\(''profiles_admin_guard''\)\)',
  'guard_last_admin() takes pg_advisory_xact_lock(hashtext(''profiles_admin_guard''))');
select is_definer('public', 'guard_last_admin', array[]::name[], 'guard_last_admin() is security definer');
select is(
  (select proconfig from pg_proc where oid = to_regprocedure('public.guard_last_admin()')),
  array['search_path=""'], 'guard_last_admin() has an empty search_path');

-- updated_at: set by the trigger on every update, whatever the statement says
select lives_ok(
  $$update public.profiles set full_name = 'Touched', updated_at = '2000-01-01 00:00:00+00' where id = '30000000-0000-0000-0000-000000000003'$$,
  'an update that tries to write updated_at succeeds');
select is(
  (select updated_at = now() from public.profiles where id = '30000000-0000-0000-0000-000000000003'),
  true, 'profiles_set_updated_at overwrites updated_at with now()');

select * from finish();
rollback;
