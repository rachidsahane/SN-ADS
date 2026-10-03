-- Migration 1: on_auth_user_created -> public.handle_new_user() (DATA_MODEL 4.1).
-- The profile is created by the trigger; the role is NEVER read from user metadata (SEC-04).
begin;
\ir _helpers.psql
select plan(25);

-- (a) a profile is created with the email copied, role marketer, active
select tests.insert_auth_user('20000000-0000-0000-0000-000000000001', 'jane@x.test',
  '{"full_name": "Jane Doe"}'::jsonb);
select is(
  (select count(*)::int from public.profiles where id = '20000000-0000-0000-0000-000000000001'),
  1, '(a) inserting into auth.users creates exactly one profile');
select is(
  (select email from public.profiles where id = '20000000-0000-0000-0000-000000000001'),
  'jane@x.test', '(a) the email is copied from auth.users');
select is(
  (select role::text from public.profiles where id = '20000000-0000-0000-0000-000000000001'),
  'marketer', '(a) the role is marketer');
select is(
  (select is_active from public.profiles where id = '20000000-0000-0000-0000-000000000001'),
  true, '(a) the profile is active');

-- (b) full_name comes from the metadata
select is(
  (select full_name from public.profiles where id = '20000000-0000-0000-0000-000000000001'),
  'Jane Doe', '(b) full_name is taken from raw_user_meta_data');

-- (c) without metadata, the local part of the email
select tests.insert_auth_user('20000000-0000-0000-0000-000000000002', 'jane@x.test.local');
select is(
  (select full_name from public.profiles where id = '20000000-0000-0000-0000-000000000002'),
  'jane', '(c) without metadata, full_name is the local part of the email');

-- (d) privilege escalation through metadata is ignored (SEC-04)
select tests.insert_auth_user('20000000-0000-0000-0000-000000000003', 'escalate@x.test',
  '{"role": "admin", "full_name": "X"}'::jsonb, '{"provider": "email", "role": "admin"}'::jsonb);
select is(
  (select role::text from public.profiles where id = '20000000-0000-0000-0000-000000000003'),
  'marketer', '(d) role "admin" in user and app metadata is ignored: the profile is a marketer');
select is(
  (select full_name from public.profiles where id = '20000000-0000-0000-0000-000000000003'),
  'X', '(d) the name from the same metadata is still used');

-- (e) hardened name rule: a blank or oversized name must never abort user creation
select lives_ok(
  $$select tests.insert_auth_user('20000000-0000-0000-0000-000000000004', 'blank@x.test', '{"full_name": ""}'::jsonb)$$,
  '(e) an empty full_name does not abort user creation');
select is(
  (select full_name from public.profiles where id = '20000000-0000-0000-0000-000000000004'),
  'blank', '(e) an empty full_name falls back to the local part of the email');

select lives_ok(
  $$select tests.insert_auth_user('20000000-0000-0000-0000-000000000005', 'spaces@x.test', '{"full_name": "     "}'::jsonb)$$,
  '(e) a full_name made of spaces does not abort user creation');
select is(
  (select full_name from public.profiles where id = '20000000-0000-0000-0000-000000000005'),
  'spaces', '(e) a full_name made of spaces falls back to the local part of the email');

select lives_ok(
  format($$select tests.insert_auth_user('20000000-0000-0000-0000-000000000006', 'long@x.test', jsonb_build_object('full_name', %L))$$,
    repeat('n', 200)),
  '(e) a 200-character full_name does not abort user creation');
select is(
  (select char_length(full_name) from public.profiles where id = '20000000-0000-0000-0000-000000000006'),
  120, '(e) a 200-character full_name is cut to 120 characters');

select lives_ok(
  format($$select tests.insert_auth_user('20000000-0000-0000-0000-000000000007', %L)$$, repeat('a', 150) || '@x.test'),
  '(e) a very long email local part does not abort user creation');
select is(
  (select char_length(full_name) from public.profiles where id = '20000000-0000-0000-0000-000000000007'),
  120, '(e) the local-part fallback is cut to 120 characters');

select lives_ok(
  $$select tests.insert_auth_user('20000000-0000-0000-0000-000000000008', '@x.test')$$,
  '(e) an email without local part does not abort user creation');
select is(
  (select full_name from public.profiles where id = '20000000-0000-0000-0000-000000000008'),
  'User', '(e) last resort full_name is "User"');

-- (f) the function itself: definer, empty search_path, not callable by API roles
select is_definer('public', 'handle_new_user', array[]::name[], 'handle_new_user() is security definer');
select is(
  (select proconfig from pg_proc where oid = to_regprocedure('public.handle_new_user()')),
  array['search_path=""'], 'handle_new_user() has an empty search_path');
select is(
  (select has_function_privilege('anon', to_regprocedure('public.handle_new_user()'), 'EXECUTE')),
  false, 'anon cannot execute handle_new_user()');
select is(
  (select has_function_privilege('authenticated', to_regprocedure('public.handle_new_user()'), 'EXECUTE')),
  false, 'authenticated cannot execute handle_new_user()');
select is(
  (select has_function_privilege('service_role', to_regprocedure('public.handle_new_user()'), 'EXECUTE')),
  false, 'service_role cannot execute handle_new_user()');
select is(
  (select has_function_privilege('public', to_regprocedure('public.handle_new_user()'), 'EXECUTE')),
  false, 'PUBLIC cannot execute handle_new_user()');

-- (g) deleting the user deletes the profile (cascade)
delete from auth.users where id = '20000000-0000-0000-0000-000000000001';
select is(
  (select count(*)::int from public.profiles where id = '20000000-0000-0000-0000-000000000001'),
  0, '(g) deleting the auth user deletes the profile');

select * from finish();
rollback;
