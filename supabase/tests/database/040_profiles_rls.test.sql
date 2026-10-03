-- Migration 1: row level security and grants of public.profiles (DATA_MODEL 6).
--   select : own row while active, or every row for an active admin   (profiles_select_own_or_admin)
--   update : active admin on ANOTHER profile only, columns full_name / role / is_active (profiles_update_by_admin)
--   insert / delete : nobody through the API (the trigger creates profiles; cascade deletes them)
-- Every policy has a positive and a negative test. "0 rows modified" is how RLS refuses an UPDATE;
-- a missing privilege raises 42501 instead.
begin;
\ir _helpers.psql
select plan(45);

-- Fixtures (ids: 4000...0001 .. 0006). Created as the owner; admins first so the guard never objects.
select tests.deactivate_existing_admins();
select tests.create_user('40000000-0000-0000-0000-000000000001', 'rls-admin-a@x.test', 'Admin A', 'admin');
select tests.create_user('40000000-0000-0000-0000-000000000002', 'rls-admin-b@x.test', 'Admin B', 'admin');
select tests.create_user('40000000-0000-0000-0000-000000000003', 'rls-market-1@x.test', 'Marketer 1');
select tests.create_user('40000000-0000-0000-0000-000000000004', 'rls-market-2@x.test', 'Marketer 2');
select tests.create_user('40000000-0000-0000-0000-000000000005', 'rls-market-off@x.test', 'Marketer Off', 'marketer', false);
select tests.create_user('40000000-0000-0000-0000-000000000006', 'rls-admin-off@x.test', 'Admin Off', 'admin', false);

-- ---------------------------------------------------------------------------------------------------------
-- SELECT: profiles_select_own_or_admin
-- ---------------------------------------------------------------------------------------------------------
select tests.authenticate_as('40000000-0000-0000-0000-000000000003');
select is((select count(*)::int from public.profiles), 1, 'select (+): an active marketer sees exactly one row');
select is((select id from public.profiles), '40000000-0000-0000-0000-000000000003'::uuid,
  'select (+): and that row is their own');
select is((select count(*)::int from public.profiles where id = '40000000-0000-0000-0000-000000000004'), 0,
  'select (-): an active marketer does not see another profile');

select tests.authenticate_as('40000000-0000-0000-0000-000000000001');
select is(
  (select count(*)::int from public.profiles where id::text like '40000000-0000-0000-0000-00000000000_'),
  6, 'select (+): an active admin sees every profile (active and inactive ones)');

select tests.authenticate_as('40000000-0000-0000-0000-000000000005');
select is((select count(*)::int from public.profiles), 0, 'select (-): a deactivated marketer sees nothing, not even their own row');

select tests.authenticate_as('40000000-0000-0000-0000-000000000006');
select is((select count(*)::int from public.profiles), 0, 'select (-): a deactivated admin sees nothing');

select tests.authenticate_as_anon();
select throws_ok($$select * from public.profiles$$, '42501', null, 'select (-): anon is refused (no privilege)');

-- ---------------------------------------------------------------------------------------------------------
-- UPDATE: profiles_update_by_admin
-- ---------------------------------------------------------------------------------------------------------
select tests.authenticate_as('40000000-0000-0000-0000-000000000001');
select is(
  tests.exec_count($$update public.profiles set full_name = 'Renamed by admin' where id = '40000000-0000-0000-0000-000000000004'$$),
  1::bigint, 'update (+): an active admin updates full_name of another profile (1 row)');
select is((select full_name from public.profiles where id = '40000000-0000-0000-0000-000000000004'),
  'Renamed by admin', 'update (+): and the change is effective');
select is(
  tests.exec_count($$update public.profiles set role = 'admin' where id = '40000000-0000-0000-0000-000000000004'$$),
  1::bigint, 'update (+): an active admin updates role of another profile (1 row)');
select is((select role::text from public.profiles where id = '40000000-0000-0000-0000-000000000004'),
  'admin', 'update (+): and the new role is effective');
select is(
  tests.exec_count($$update public.profiles set is_active = false where id = '40000000-0000-0000-0000-000000000004'$$),
  1::bigint, 'update (+): an active admin updates is_active of another profile (1 row)');
select is((select is_active from public.profiles where id = '40000000-0000-0000-0000-000000000004'),
  false, 'update (+): and the deactivation is effective');

-- an admin cannot touch their own row (no self-demotion, no self-deactivation)
select is(
  tests.exec_count($$update public.profiles set full_name = 'Self rename' where id = '40000000-0000-0000-0000-000000000001'$$),
  0::bigint, 'update (-): an admin cannot update their own full_name (0 rows)');
select is(
  tests.exec_count($$update public.profiles set role = 'marketer' where id = '40000000-0000-0000-0000-000000000001'$$),
  0::bigint, 'update (-): an admin cannot demote themselves (0 rows)');
select is(
  tests.exec_count($$update public.profiles set is_active = false where id = '40000000-0000-0000-0000-000000000001'$$),
  0::bigint, 'update (-): an admin cannot deactivate themselves (0 rows)');

-- columns outside full_name / role / is_active are refused by the grants
select throws_ok(
  $$update public.profiles set email = 'hijack@x.test' where id = '40000000-0000-0000-0000-000000000003'$$,
  '42501', null, 'update (-): an admin cannot update email (column privilege)');
select throws_ok(
  $$update public.profiles set id = gen_random_uuid() where id = '40000000-0000-0000-0000-000000000003'$$,
  '42501', null, 'update (-): an admin cannot update id (column privilege)');
select throws_ok(
  $$update public.profiles set created_at = now() where id = '40000000-0000-0000-0000-000000000003'$$,
  '42501', null, 'update (-): an admin cannot update created_at (column privilege)');
select throws_ok(
  $$update public.profiles set updated_at = now() where id = '40000000-0000-0000-0000-000000000003'$$,
  '42501', null, 'update (-): an admin cannot update updated_at (column privilege)');

-- marketers: nothing, including privilege escalation on their own row
select tests.authenticate_as('40000000-0000-0000-0000-000000000003');
select is(
  tests.exec_count($$update public.profiles set full_name = 'Self rename' where id = '40000000-0000-0000-0000-000000000003'$$),
  0::bigint, 'update (-): a marketer cannot update their own row (0 rows)');
select is(
  tests.exec_count($$update public.profiles set role = 'admin' where id = '40000000-0000-0000-0000-000000000003'$$),
  0::bigint, 'update (-): a marketer cannot promote themselves (0 rows)');
select is(
  tests.exec_count($$update public.profiles set full_name = 'Not mine' where id = '40000000-0000-0000-0000-000000000002'$$),
  0::bigint, 'update (-): a marketer cannot update another profile (0 rows)');
select is(
  tests.exec_count($$update public.profiles set is_active = false where id = '40000000-0000-0000-0000-000000000002'$$),
  0::bigint, 'update (-): a marketer cannot deactivate an admin (0 rows)');

-- a deactivated admin has no admin power left
select tests.authenticate_as('40000000-0000-0000-0000-000000000006');
select is(
  tests.exec_count($$update public.profiles set full_name = 'Ghost' where id = '40000000-0000-0000-0000-000000000003'$$),
  0::bigint, 'update (-): a deactivated admin cannot update another profile (0 rows)');

-- anon
select tests.authenticate_as_anon();
select throws_ok(
  $$update public.profiles set full_name = 'Anon' where id = '40000000-0000-0000-0000-000000000003'$$,
  '42501', null, 'update (-): anon is refused (no privilege)');

-- None of the refused updates changed anything (checked as the owner)
select tests.reset_role();
select is(
  (select array_agg(full_name || '/' || role::text || '/' || is_active::text order by id)
     from public.profiles where id in (
       '40000000-0000-0000-0000-000000000001', '40000000-0000-0000-0000-000000000002',
       '40000000-0000-0000-0000-000000000003', '40000000-0000-0000-0000-000000000006')),
  array['Admin A/admin/true', 'Admin B/admin/true', 'Marketer 1/marketer/true', 'Admin Off/admin/false'],
  'the refused updates left the other rows untouched');

-- ---------------------------------------------------------------------------------------------------------
-- INSERT and DELETE: nobody through the API
-- ---------------------------------------------------------------------------------------------------------
select tests.authenticate_as('40000000-0000-0000-0000-000000000001');
select throws_ok(
  $$insert into public.profiles (id, email, full_name, role) values (gen_random_uuid(), 'new-admin@x.test', 'New', 'admin')$$,
  '42501', null, 'insert (-): an active admin cannot insert a profile');
select throws_ok(
  $$delete from public.profiles where id = '40000000-0000-0000-0000-000000000003'$$,
  '42501', null, 'delete (-): an active admin cannot delete a profile');

select tests.authenticate_as('40000000-0000-0000-0000-000000000003');
select throws_ok(
  $$insert into public.profiles (id, email, full_name) values (gen_random_uuid(), 'new-marketer@x.test', 'New')$$,
  '42501', null, 'insert (-): a marketer cannot insert a profile');
select throws_ok(
  $$delete from public.profiles where id = '40000000-0000-0000-0000-000000000003'$$,
  '42501', null, 'delete (-): a marketer cannot delete their own profile');

select tests.authenticate_as_anon();
select throws_ok(
  $$insert into public.profiles (id, email, full_name) values (gen_random_uuid(), 'new-anon@x.test', 'New')$$,
  '42501', null, 'insert (-): anon cannot insert a profile');
select throws_ok(
  $$delete from public.profiles where id = '40000000-0000-0000-0000-000000000003'$$,
  '42501', null, 'delete (-): anon cannot delete a profile');

-- ---------------------------------------------------------------------------------------------------------
-- Privileges (the grants behind the policies)
-- ---------------------------------------------------------------------------------------------------------
select tests.reset_role();
select is(has_column_privilege('authenticated', 'public.profiles', 'role', 'UPDATE'), true,
  'grant: authenticated may update column role (the policy restricts it to admins)');
select is(has_column_privilege('authenticated', 'public.profiles', 'full_name', 'UPDATE'), true,
  'grant: authenticated may update column full_name');
select is(has_column_privilege('authenticated', 'public.profiles', 'is_active', 'UPDATE'), true,
  'grant: authenticated may update column is_active');
select is(has_column_privilege('authenticated', 'public.profiles', 'email', 'UPDATE'), false,
  'grant: authenticated may NOT update column email');
select is(has_column_privilege('authenticated', 'public.profiles', 'id', 'UPDATE'), false,
  'grant: authenticated may NOT update column id');
select is(has_table_privilege('authenticated', 'public.profiles', 'SELECT'), true,
  'grant: authenticated may select');
select is(has_table_privilege('authenticated', 'public.profiles', 'INSERT'), false,
  'grant: authenticated may NOT insert');
select is(has_table_privilege('authenticated', 'public.profiles', 'DELETE'), false,
  'grant: authenticated may NOT delete');
select is(has_table_privilege('authenticated', 'public.profiles', 'TRUNCATE'), false,
  'grant: authenticated may NOT truncate');
select is(has_table_privilege('anon', 'public.profiles', 'SELECT'), false,
  'grant: anon may NOT select');
select is(has_any_column_privilege('anon', 'public.profiles', 'SELECT,INSERT,UPDATE,REFERENCES'), false,
  'grant: anon has no column privilege at all');
select is(
  (select count(*)::int from pg_policies where schemaname = 'public' and tablename = 'profiles'),
  2, 'exactly two policies exist on profiles (select, update): no insert or delete policy');

select * from finish();
rollback;
