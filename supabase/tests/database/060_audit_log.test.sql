-- Migration 2: public.audit_log (DATA_MODEL 4.6, 6): structure, checks, forced RLS, append-only rights.
begin;
\ir _helpers.psql
select plan(58);

select has_table('public', 'audit_log', 'table public.audit_log exists');

-- Structure
select col_type_is('public', 'audit_log', 'id', 'bigint', 'id is bigint');
select col_type_is('public', 'audit_log', 'actor_id', 'uuid', 'actor_id is uuid');
select col_type_is('public', 'audit_log', 'action', 'text', 'action is text');
select col_type_is('public', 'audit_log', 'target_type', 'text', 'target_type is text');
select col_type_is('public', 'audit_log', 'target_id', 'text', 'target_id is text');
select col_type_is('public', 'audit_log', 'metadata', 'jsonb', 'metadata is jsonb');
select col_type_is('public', 'audit_log', 'created_at', 'timestamp with time zone', 'created_at is timestamptz');
select col_is_pk('public', 'audit_log', 'id', 'id is the primary key');
select is(
  (select attidentity::text from pg_attribute where attrelid = to_regclass('public.audit_log') and attname = 'id'),
  'a', 'id is GENERATED ALWAYS AS IDENTITY');
select col_is_null('public', 'audit_log', 'actor_id', 'actor_id is nullable (system actions)');
select col_not_null('public', 'audit_log', 'action', 'action is not null');
select col_not_null('public', 'audit_log', 'target_type', 'target_type is not null');
select col_not_null('public', 'audit_log', 'target_id', 'target_id is not null');
select col_not_null('public', 'audit_log', 'metadata', 'metadata is not null');
select col_not_null('public', 'audit_log', 'created_at', 'created_at is not null');
select is(
  (select column_default from information_schema.columns
    where table_schema = 'public' and table_name = 'audit_log' and column_name = 'metadata'),
  $$'{}'::jsonb$$, 'metadata defaults to an empty object');
select is(
  (select column_default from information_schema.columns
    where table_schema = 'public' and table_name = 'audit_log' and column_name = 'created_at'),
  'now()', 'created_at defaults to now()');
select fk_ok('public', 'audit_log', 'actor_id', 'public', 'profiles', 'id', 'actor_id references profiles(id)');
select is(
  (select confdeltype::text from pg_constraint
    where conrelid = to_regclass('public.audit_log') and contype = 'f' and confrelid = to_regclass('public.profiles')),
  'n', 'the foreign key to profiles is on delete set null');
select is(
  (select indexdef from pg_indexes where schemaname = 'public' and indexname = 'audit_log_created_idx'),
  'CREATE INDEX audit_log_created_idx ON public.audit_log USING btree (created_at DESC, id DESC)',
  'index audit_log_created_idx on (created_at desc, id desc)');
select is((select relrowsecurity from pg_class where oid = to_regclass('public.audit_log')), true,
  'RLS is enabled on public.audit_log');
select is((select relforcerowsecurity from pg_class where oid = to_regclass('public.audit_log')), true,
  'RLS is forced on public.audit_log');

-- Check constraints (rows inserted as the owner)
select lives_ok(
  format($$insert into public.audit_log (action, target_type, target_id) values (%L, 'user', 'check-action')$$, a),
  'action accepted: ' || a)
from unnest(array[
  'user.invited', 'user.role_changed', 'user.deactivated', 'user.reactivated',
  'upload.accepted', 'upload.failed',
  'model.training_requested', 'model.training_succeeded', 'model.training_failed',
  'model.activated']) as a;
select throws_ok(
  $$insert into public.audit_log (action, target_type, target_id) values ('user.deleted', 'user', 'x')$$,
  '23514', null, 'an unknown action is refused');
select lives_ok(
  format($$insert into public.audit_log (action, target_type, target_id) values ('user.invited', %L, 'check-type')$$, t),
  'target_type accepted: ' || t)
from unnest(array['user', 'upload', 'model_version']) as t;
select throws_ok(
  $$insert into public.audit_log (action, target_type, target_id) values ('user.invited', 'prediction', 'x')$$,
  '23514', null, 'an unknown target_type is refused');

-- Defaults really apply
select is(
  (select metadata from public.audit_log where target_id = 'check-type' limit 1),
  '{}'::jsonb, 'a row inserted without metadata gets {}');

-- FK on delete set null: deleting the actor keeps the line
select tests.create_user('60000000-0000-0000-0000-000000000009', 'audit-actor@x.test', 'Audit Actor');
insert into public.audit_log (actor_id, action, target_type, target_id)
  values ('60000000-0000-0000-0000-000000000009', 'user.invited', 'user', 'actor-delete');
delete from auth.users where id = '60000000-0000-0000-0000-000000000009';
select is(
  (select count(*)::int from public.audit_log where target_id = 'actor-delete' and actor_id is null),
  1, 'deleting the actor keeps the audit line and sets actor_id to null');

-- ---------------------------------------------------------------------------------------------------------
-- RLS: audit_log_select_admin
-- ---------------------------------------------------------------------------------------------------------
select tests.deactivate_existing_admins();
select tests.create_user('60000000-0000-0000-0000-000000000001', 'audit-admin@x.test', 'Admin', 'admin');
select tests.create_user('60000000-0000-0000-0000-000000000002', 'audit-admin-off@x.test', 'Admin Off', 'admin', false);
select tests.create_user('60000000-0000-0000-0000-000000000003', 'audit-market@x.test', 'Marketer');
insert into public.audit_log (action, target_type, target_id) values
  ('user.invited', 'user', 'sel-1'),
  ('upload.accepted', 'upload', 'sel-2');

select tests.authenticate_as('60000000-0000-0000-0000-000000000001');
select is((select count(*)::int from public.audit_log where target_id like 'sel-%'), 2,
  'select (+): an active admin reads the audit lines');

select tests.authenticate_as('60000000-0000-0000-0000-000000000003');
select is((select count(*)::int from public.audit_log), 0, 'select (-): an active marketer reads nothing');

select tests.authenticate_as('60000000-0000-0000-0000-000000000002');
select is((select count(*)::int from public.audit_log), 0, 'select (-): a deactivated admin reads nothing');

select tests.authenticate_as_anon();
select throws_ok($$select * from public.audit_log$$, '42501', null, 'select (-): anon is refused');

-- Direct writes through the API roles are refused (log_audit() is the only door, see 070)
select tests.authenticate_as('60000000-0000-0000-0000-000000000001');
select throws_ok(
  $$insert into public.audit_log (action, target_type, target_id) values ('user.invited', 'user', 'direct')$$,
  '42501', null, 'insert (-): an active admin cannot insert directly');
select throws_ok(
  $$update public.audit_log set target_id = 'tampered' where target_id = 'sel-1'$$,
  '42501', null, 'update (-): an active admin cannot update an audit line');
select throws_ok(
  $$delete from public.audit_log where target_id = 'sel-1'$$,
  '42501', null, 'delete (-): an active admin cannot delete an audit line');

select tests.authenticate_as('60000000-0000-0000-0000-000000000003');
select throws_ok(
  $$insert into public.audit_log (action, target_type, target_id) values ('user.invited', 'user', 'direct')$$,
  '42501', null, 'insert (-): a marketer cannot insert directly');

-- service_role (worker, app.cli.*): insert only, even though it bypasses RLS
select tests.authenticate_as_service_role();
select lives_ok(
  $$insert into public.audit_log (action, target_type, target_id) values ('model.training_succeeded', 'model_version', 'by-service')$$,
  'service_role can insert an audit line');
select throws_ok(
  $$update public.audit_log set target_id = 'tampered' where target_id = 'by-service'$$,
  '42501', null, 'service_role cannot update an audit line');
select throws_ok(
  $$delete from public.audit_log where target_id = 'by-service'$$,
  '42501', null, 'service_role cannot delete an audit line');
select throws_ok(
  $$truncate public.audit_log$$,
  '42501', null, 'service_role cannot truncate the audit log');

-- Anon: write refused as well
select tests.authenticate_as_anon();
select throws_ok(
  $$insert into public.audit_log (action, target_type, target_id) values ('user.invited', 'user', 'anon')$$,
  '42501', null, 'insert (-): anon cannot insert');

-- Nothing was altered by the refused statements
select tests.reset_role();
select is(
  (select count(*)::int from public.audit_log where target_id in ('sel-1', 'sel-2', 'by-service')), 3,
  'the audit lines are intact after the refused update, delete and truncate');

-- Privileges
select is(
  (select count(*)::int from unnest(array['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER']) as p
    where has_table_privilege('anon', 'public.audit_log', p)),
  0, 'grant: anon has no privilege on audit_log');
select is(
  (select array_agg(p order by p) from unnest(array['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER']) as p
    where has_table_privilege('authenticated', 'public.audit_log', p)),
  array['SELECT'], 'grant: authenticated has SELECT only on audit_log');
select is(
  (select array_agg(p order by p) from unnest(array['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER']) as p
    where has_table_privilege('service_role', 'public.audit_log', p)),
  array['INSERT'], 'grant: service_role has INSERT only on audit_log (append-only)');
select is(
  (select count(*)::int from pg_policies where schemaname = 'public' and tablename = 'audit_log'),
  1, 'exactly one policy exists on audit_log (select for admins)');

select * from finish();
rollback;
