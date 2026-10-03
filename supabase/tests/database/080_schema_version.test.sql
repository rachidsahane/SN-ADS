-- Migration 1: public.schema_version(), the readiness probe helper (decision D-049 of phase 1).
-- It returns only the identifier of the last applied migration and is the ONLY function anon may execute
-- (SECURITY_NOTES 3.7). It reads supabase_migrations.schema_migrations, which exists once the Supabase CLI
-- has applied migrations: make test-db always runs after `make db-migrate`.
begin;
\ir _helpers.psql
select plan(13);

select set_config('tests.expected_version', (select max(version) from supabase_migrations.schema_migrations), true);

select isnt(current_setting('tests.expected_version'), '', 'precondition: at least one migration is recorded');

select function_returns('public', 'schema_version', array[]::name[], 'text', 'schema_version() returns text');
select matches(public.schema_version(), '^\d{14}$', 'schema_version() is a 14-digit migration identifier');
select is(public.schema_version(), current_setting('tests.expected_version'),
  'schema_version() equals the last applied migration');

-- Callable by anon and authenticated, with the same answer
select tests.authenticate_as_anon();
select is(public.schema_version(), current_setting('tests.expected_version'), 'anon can call schema_version()');
select tests.authenticate_as('80000000-0000-0000-0000-000000000001');
select is(public.schema_version(), current_setting('tests.expected_version'), 'authenticated can call schema_version()');
select tests.reset_role();

-- Not callable by service_role nor PUBLIC; anon and authenticated hold the privilege
select is(has_function_privilege('anon', to_regprocedure('public.schema_version()'), 'EXECUTE'), true,
  'anon holds EXECUTE on schema_version()');
select is(has_function_privilege('authenticated', to_regprocedure('public.schema_version()'), 'EXECUTE'), true,
  'authenticated holds EXECUTE on schema_version()');
select is(has_function_privilege('service_role', to_regprocedure('public.schema_version()'), 'EXECUTE'), false,
  'service_role does not hold EXECUTE on schema_version()');
select is(has_function_privilege('public', to_regprocedure('public.schema_version()'), 'EXECUTE'), false,
  'PUBLIC does not hold EXECUTE on schema_version()');

-- Secure definition
select is_definer('public', 'schema_version', array[]::name[], 'schema_version() is security definer');
select is(
  (select proconfig from pg_proc where oid = to_regprocedure('public.schema_version()')),
  array['search_path=""'], 'schema_version() has an empty search_path');

-- It exposes nothing but a version string: it cannot be used to read the migrations table through anon
select tests.authenticate_as_anon();
select throws_ok($$select * from supabase_migrations.schema_migrations$$, '42501', null,
  'anon cannot read supabase_migrations.schema_migrations directly');

select * from finish();
rollback;
