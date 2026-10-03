-- Migration 1: structure of public.profiles (DATA_MODEL 4.1): columns, defaults, keys, checks, index,
-- triggers, forced RLS. Behaviour of the triggers is covered by 020 and 030, policies by 040.
begin;
\ir _helpers.psql
select plan(40);

select has_table('public', 'profiles', 'table public.profiles exists');

-- Columns: types
select col_type_is('public', 'profiles', 'id', 'uuid', 'id is uuid');
select col_type_is('public', 'profiles', 'email', 'text', 'email is text');
select col_type_is('public', 'profiles', 'full_name', 'text', 'full_name is text');
select col_type_is('public', 'profiles', 'role', 'public', 'app_role', 'role is public.app_role');
select col_type_is('public', 'profiles', 'is_active', 'boolean', 'is_active is boolean');
select col_type_is('public', 'profiles', 'created_at', 'timestamp with time zone', 'created_at is timestamptz');
select col_type_is('public', 'profiles', 'updated_at', 'timestamp with time zone', 'updated_at is timestamptz');

-- Columns: not null
select col_not_null('public', 'profiles', 'id', 'id is not null');
select col_not_null('public', 'profiles', 'email', 'email is not null');
select col_not_null('public', 'profiles', 'full_name', 'full_name is not null');
select col_not_null('public', 'profiles', 'role', 'role is not null');
select col_not_null('public', 'profiles', 'is_active', 'is_active is not null');
select col_not_null('public', 'profiles', 'created_at', 'created_at is not null');
select col_not_null('public', 'profiles', 'updated_at', 'updated_at is not null');

-- Columns: defaults
select is(
  (select column_default from information_schema.columns
    where table_schema = 'public' and table_name = 'profiles' and column_name = 'role'),
  $$'marketer'::app_role$$, 'role defaults to marketer');
select is(
  (select column_default from information_schema.columns
    where table_schema = 'public' and table_name = 'profiles' and column_name = 'is_active'),
  'true', 'is_active defaults to true');
select is(
  (select column_default from information_schema.columns
    where table_schema = 'public' and table_name = 'profiles' and column_name = 'created_at'),
  'now()', 'created_at defaults to now()');
select is(
  (select column_default from information_schema.columns
    where table_schema = 'public' and table_name = 'profiles' and column_name = 'updated_at'),
  'now()', 'updated_at defaults to now()');

-- Keys
select col_is_pk('public', 'profiles', 'id', 'id is the primary key');
select fk_ok('public', 'profiles', 'id', 'auth', 'users', 'id', 'id references auth.users(id)');
select is(
  (select confdeltype::text from pg_constraint
    where conrelid = to_regclass('public.profiles') and contype = 'f'
      and confrelid = to_regclass('auth.users')),
  'c', 'the foreign key to auth.users is on delete cascade');
select col_is_unique('public', 'profiles', 'email', 'email is unique');

-- Fixtures for the constraint probes (run as the owner, like a migration or an admin tool)
select tests.create_user('10000000-0000-0000-0000-000000000001', 'unique-a@example.test', 'Unique A');
select tests.create_user('10000000-0000-0000-0000-000000000002', 'unique-b@example.test', 'Unique B');

select throws_ok(
  $$update public.profiles set email = 'unique-a@example.test' where id = '10000000-0000-0000-0000-000000000002'$$,
  '23505', null, 'a duplicate email is refused (unique violation)');

select throws_ok(
  $$update public.profiles set full_name = '' where id = '10000000-0000-0000-0000-000000000002'$$,
  '23514', null, 'full_name of length 0 is refused');
select throws_ok(
  $$update public.profiles set full_name = repeat('x', 121) where id = '10000000-0000-0000-0000-000000000002'$$,
  '23514', null, 'full_name of length 121 is refused');
select lives_ok(
  $$update public.profiles set full_name = 'x' where id = '10000000-0000-0000-0000-000000000002'$$,
  'full_name of length 1 is accepted');
select lives_ok(
  $$update public.profiles set full_name = repeat('x', 120) where id = '10000000-0000-0000-0000-000000000002'$$,
  'full_name of length 120 is accepted');

-- Index
select has_index('public', 'profiles', 'profiles_role_active_idx', array['role', 'is_active'],
  'index profiles_role_active_idx on (role, is_active)');

-- Triggers: presence, timing, function
select has_trigger('public', 'profiles', 'profiles_guard_last_admin', 'trigger profiles_guard_last_admin exists');
select has_trigger('public', 'profiles', 'profiles_set_updated_at', 'trigger profiles_set_updated_at exists');
select has_trigger('auth', 'users', 'on_auth_user_created', 'trigger on_auth_user_created exists on auth.users');
select trigger_is('public', 'profiles', 'profiles_guard_last_admin', 'public', 'guard_last_admin',
  'profiles_guard_last_admin calls public.guard_last_admin()');
select trigger_is('public', 'profiles', 'profiles_set_updated_at', 'public', 'set_updated_at',
  'profiles_set_updated_at calls public.set_updated_at()');
select trigger_is('auth', 'users', 'on_auth_user_created', 'public', 'handle_new_user',
  'on_auth_user_created calls public.handle_new_user()');
-- tgtype bits: 1 = row, 2 = before, 4 = insert, 16 = update. before update for each row = 19, after insert = 5.
select is(
  (select tgtype::int from pg_trigger
    where tgname = 'profiles_guard_last_admin' and tgrelid = to_regclass('public.profiles')),
  19, 'profiles_guard_last_admin is BEFORE UPDATE FOR EACH ROW');
select is(
  (select tgtype::int from pg_trigger
    where tgname = 'profiles_set_updated_at' and tgrelid = to_regclass('public.profiles')),
  19, 'profiles_set_updated_at is BEFORE UPDATE FOR EACH ROW');
select is(
  (select tgtype::int from pg_trigger
    where tgname = 'on_auth_user_created' and tgrelid = to_regclass('auth.users')),
  5, 'on_auth_user_created is AFTER INSERT FOR EACH ROW');

-- Row level security: enabled AND forced
select is(
  (select relrowsecurity from pg_class where oid = to_regclass('public.profiles')),
  true, 'RLS is enabled on public.profiles');
select is(
  (select relforcerowsecurity from pg_class where oid = to_regclass('public.profiles')),
  true, 'RLS is forced on public.profiles');

select * from finish();
rollback;
