-- Migration 1: public.is_admin() and public.is_active_user() (DATA_MODEL 5, SECURITY_NOTES 3.7).
begin;
\ir _helpers.psql
select plan(22);

select tests.deactivate_existing_admins();
select tests.create_user('50000000-0000-0000-0000-000000000001', 'fn-admin@x.test', 'Admin', 'admin');
select tests.create_user('50000000-0000-0000-0000-000000000002', 'fn-admin-off@x.test', 'Admin Off', 'admin', false);
select tests.create_user('50000000-0000-0000-0000-000000000003', 'fn-market@x.test', 'Marketer');
select tests.create_user('50000000-0000-0000-0000-000000000004', 'fn-market-off@x.test', 'Marketer Off', 'marketer', false);

-- Truth table, as the authenticated role the API uses
select tests.authenticate_as('50000000-0000-0000-0000-000000000001');
select is(public.is_admin(), true, 'active admin: is_admin() is true');
select is(public.is_active_user(), true, 'active admin: is_active_user() is true');

select tests.authenticate_as('50000000-0000-0000-0000-000000000002');
select is(public.is_admin(), false, 'inactive admin: is_admin() is false');
select is(public.is_active_user(), false, 'inactive admin: is_active_user() is false');

select tests.authenticate_as('50000000-0000-0000-0000-000000000003');
select is(public.is_admin(), false, 'active marketer: is_admin() is false');
select is(public.is_active_user(), true, 'active marketer: is_active_user() is true');

select tests.authenticate_as('50000000-0000-0000-0000-000000000004');
select is(public.is_admin(), false, 'inactive marketer: is_admin() is false');
select is(public.is_active_user(), false, 'inactive marketer: is_active_user() is false');

-- A token whose subject has no profile
select tests.authenticate_as('50000000-0000-0000-0000-0000000000ff');
select is(public.is_admin(), false, 'unknown user id: is_admin() is false');
select is(public.is_active_user(), false, 'unknown user id: is_active_user() is false');

-- No token at all: refused for anon, false for the owner (auth.uid() is null)
select tests.authenticate_as_anon();
select throws_ok($$select public.is_admin()$$, '42501', null, 'anon cannot execute is_admin()');
select throws_ok($$select public.is_active_user()$$, '42501', null, 'anon cannot execute is_active_user()');

select tests.reset_role();
select is(public.is_admin(), false, 'without any user id, is_admin() is false');
select is(public.is_active_user(), false, 'without any user id, is_active_user() is false');

-- Definition (SECURITY_NOTES 3.7: security definer, empty search_path, execute for authenticated only)
select is_definer('public', 'is_admin', array[]::name[], 'is_admin() is security definer');
select is_definer('public', 'is_active_user', array[]::name[], 'is_active_user() is security definer');
select is(
  (select proconfig from pg_proc where oid = to_regprocedure('public.is_admin()')),
  array['search_path=""'], 'is_admin() has an empty search_path');
select is(
  (select proconfig from pg_proc where oid = to_regprocedure('public.is_active_user()')),
  array['search_path=""'], 'is_active_user() has an empty search_path');
select volatility_is('public', 'is_admin', array[]::name[], 'stable', 'is_admin() is stable');
select volatility_is('public', 'is_active_user', array[]::name[], 'stable', 'is_active_user() is stable');

-- Execute rights: authenticated only
select is(
  (select array_agg(r order by r) from unnest(array['anon', 'authenticated', 'service_role', 'public']) as r
    where has_function_privilege(r, to_regprocedure('public.is_admin()'), 'EXECUTE')),
  array['authenticated'], 'only authenticated may execute is_admin() (not anon, service_role, PUBLIC)');
select is(
  (select array_agg(r order by r) from unnest(array['anon', 'authenticated', 'service_role', 'public']) as r
    where has_function_privilege(r, to_regprocedure('public.is_active_user()'), 'EXECUTE')),
  array['authenticated'], 'only authenticated may execute is_active_user() (not anon, service_role, PUBLIC)');

select * from finish();
rollback;
