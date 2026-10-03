-- Migration 2: public.log_audit(action, target_type, target_id, metadata) (DATA_MODEL 5):
-- reserved to active admins, records actor_id = auth.uid(), role check is the first statement.
begin;
\ir _helpers.psql
select plan(19);

select tests.deactivate_existing_admins();
select tests.create_user('70000000-0000-0000-0000-000000000001', 'log-admin@x.test', 'Admin', 'admin');
select tests.create_user('70000000-0000-0000-0000-000000000002', 'log-admin-off@x.test', 'Admin Off', 'admin', false);
select tests.create_user('70000000-0000-0000-0000-000000000003', 'log-market@x.test', 'Marketer');

-- Active admin: one line, actor = caller, metadata as given
select tests.authenticate_as('70000000-0000-0000-0000-000000000001');
select lives_ok(
  $$select public.log_audit('user.invited', 'user', 'abc', '{"k": 1}'::jsonb)$$,
  'an active admin can call log_audit()');
select is((select count(*)::int from public.audit_log where target_id = 'abc'), 1,
  'log_audit() inserted exactly one line');
select is((select actor_id from public.audit_log where target_id = 'abc'),
  '70000000-0000-0000-0000-000000000001'::uuid, 'actor_id is the caller (auth.uid())');
select is((select action from public.audit_log where target_id = 'abc'), 'user.invited', 'action is recorded');
select is((select target_type from public.audit_log where target_id = 'abc'), 'user', 'target_type is recorded');
select is((select metadata from public.audit_log where target_id = 'abc'), '{"k": 1}'::jsonb, 'metadata is recorded');
select lives_ok(
  $$select public.log_audit('upload.accepted', 'upload', 'abc-null', null)$$,
  'a null metadata is accepted');
select is((select metadata from public.audit_log where target_id = 'abc-null'), '{}'::jsonb,
  'a null metadata is stored as {}');

-- Refusals
select tests.authenticate_as('70000000-0000-0000-0000-000000000003');
select throws_ok(
  $$select public.log_audit('user.invited', 'user', 'by-marketer', '{}'::jsonb)$$,
  'P0001', 'FORBIDDEN', 'an active marketer gets FORBIDDEN');

select tests.authenticate_as('70000000-0000-0000-0000-000000000002');
select throws_ok(
  $$select public.log_audit('user.invited', 'user', 'by-inactive-admin', '{}'::jsonb)$$,
  'P0001', 'FORBIDDEN', 'a deactivated admin gets FORBIDDEN');

select tests.authenticate_as_anon();
select throws_ok(
  $$select public.log_audit('user.invited', 'user', 'by-anon', '{}'::jsonb)$$,
  '42501', null, 'anon cannot execute log_audit()');

select tests.authenticate_as('70000000-0000-0000-0000-000000000001');
select throws_ok(
  $$select public.log_audit('user.deleted', 'user', 'bad-action', '{}'::jsonb)$$,
  '23514', null, 'an action outside the allowed list is refused by the check constraint');
select throws_ok(
  $$select public.log_audit('user.invited', 'prediction', 'bad-target', '{}'::jsonb)$$,
  '23514', null, 'a target_type outside the allowed list is refused by the check constraint');

-- Refused calls left no trace
select tests.reset_role();
select is(
  (select count(*)::int from public.audit_log
    where target_id in ('by-marketer', 'by-inactive-admin', 'by-anon', 'bad-action', 'bad-target')),
  0, 'refused calls left no audit line');

-- Definition
select function_returns('public', 'log_audit', array['text', 'text', 'text', 'jsonb'], 'void',
  'log_audit() returns void');
select is_definer('public', 'log_audit', array['text', 'text', 'text', 'jsonb'], 'log_audit() is security definer');
select is(
  (select proconfig from pg_proc where oid = to_regprocedure('public.log_audit(text, text, text, jsonb)')),
  array['search_path=""'], 'log_audit() has an empty search_path');
select matches(
  (select prosrc from pg_proc where oid = to_regprocedure('public.log_audit(text, text, text, jsonb)')),
  '^\s*begin\s+if not public\.is_admin\(\)',
  'the admin check is the first statement of log_audit()');
select is(
  (select array_agg(r order by r) from unnest(array['anon', 'authenticated', 'service_role', 'public']) as r
    where has_function_privilege(r, to_regprocedure('public.log_audit(text, text, text, jsonb)'), 'EXECUTE')),
  array['authenticated'], 'only authenticated may execute log_audit() (not anon, service_role, PUBLIC)');

select * from finish();
rollback;
