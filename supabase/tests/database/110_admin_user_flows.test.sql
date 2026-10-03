-- Phase 3: characterisation of the database contracts the user-management API relies on (no new object, no migration).
-- Green immediately: the policies, grants, trigger and log_audit() already exist (migrations 1 and 2). Each assertion
-- documents a rule the admin routes (invite, PATCH user, audit log) are built on; if one of them changes, the API breaks.
begin;
\ir _helpers.psql
select plan(35);

-- Update a role as the CURRENT database role and return the row's new role (null when RLS filtered the row out):
-- a data-modifying statement cannot sit in a pgTAP cursor, so it goes through a small invoker function.
create function tests.update_returning_role(p_id uuid, p_role text) returns text language plpgsql as $$
declare r text;
begin
  update public.profiles set role = p_role::public.app_role where id = p_id returning role::text into r;
  return r;
end $$;
grant execute on function tests.update_returning_role(uuid, text) to authenticated;

-- Fixtures independent of existing data. A, B, C: active admins. D: marketer (the target of most updates).
-- E: deactivated admin. F: acting marketer. G: user born with role=admin in raw_user_meta_data (must stay marketer).
select tests.deactivate_existing_admins();
select tests.create_user('b1000000-0000-0000-0000-00000000000a', 'p3-a@x.test', 'Phase3 Admin A', 'admin');
select tests.create_user('b1000000-0000-0000-0000-00000000000b', 'p3-b@x.test', 'Phase3 Admin B', 'admin');
select tests.create_user('b1000000-0000-0000-0000-00000000000c', 'p3-c@x.test', 'Phase3 Admin C', 'admin');
select tests.create_user('b1000000-0000-0000-0000-00000000000d', 'p3-d@x.test', 'Phase3 Marketer D');
select tests.create_user('b1000000-0000-0000-0000-00000000000e', 'p3-e@x.test', 'Phase3 Admin E', 'admin', false);
select tests.create_user('b1000000-0000-0000-0000-00000000000f', 'p3-f@x.test', 'Phase3 Marketer F');
select tests.insert_auth_user('b1000000-0000-0000-0000-000000000010', 'p3-g@x.test',
  '{"full_name": "Phase3 Meta G", "role": "admin"}'::jsonb);

-- 1. Invite flow, step 3: the admin's token promotes the new profile; the representation comes back (RLS select policy)
select tests.authenticate_as('b1000000-0000-0000-0000-00000000000a');
select is(tests.update_returning_role('b1000000-0000-0000-0000-00000000000d', 'admin'), 'admin',
  'admin update (+): an admin promotes a marketer and gets the updated row back (UPDATE ... RETURNING)');
select is((select role::text from public.profiles where id = 'b1000000-0000-0000-0000-00000000000d'), 'admin',
  'admin update (+): the new role is visible to the admin afterwards');

-- SEC-04: the role can only rise through the PATCH above, never through user metadata
select is((select role::text from public.profiles where id = 'b1000000-0000-0000-0000-000000000010'), 'marketer',
  'SEC-04: role=admin placed in raw_user_meta_data does not make the new profile an admin');

-- 2. Role and activity change in ONE statement (the trigger sees the final state), a third admin exists
select is(
  tests.exec_count($$update public.profiles set role = 'marketer', is_active = false where id = 'b1000000-0000-0000-0000-00000000000d'$$),
  1::bigint, 'admin update (+): role and is_active change together in one statement on another admin');
select is(
  (select role::text || '/' || is_active::text from public.profiles where id = 'b1000000-0000-0000-0000-00000000000d'),
  'marketer/false', 'admin update (+): both columns are effective after the single statement');

-- 4. Self update is silent: zero rows, no error (why the API pre-checks and answers 409 SELF_ACTION_FORBIDDEN)
select is(
  tests.exec_count($$update public.profiles set full_name = 'Renamed' where id = 'b1000000-0000-0000-0000-00000000000a'$$),
  0::bigint, 'self (-): an admin updating the own full_name touches 0 rows and raises nothing');
select is(
  tests.exec_count($$update public.profiles set role = 'marketer' where id = 'b1000000-0000-0000-0000-00000000000a'$$),
  0::bigint, 'self (-): an admin updating the own role touches 0 rows and raises nothing');
select is(
  tests.exec_count($$update public.profiles set is_active = false where id = 'b1000000-0000-0000-0000-00000000000a'$$),
  0::bigint, 'self (-): an admin updating the own is_active touches 0 rows and raises nothing');

-- 5. Column grants and non-admins
select throws_ok(
  $$update public.profiles set email = 'hijack@x.test' where id = 'b1000000-0000-0000-0000-00000000000f'$$,
  '42501', null, 'grant (-): an admin cannot change an e-mail');
select throws_ok(
  $$update public.profiles set id = gen_random_uuid() where id = 'b1000000-0000-0000-0000-00000000000f'$$,
  '42501', null, 'grant (-): an admin cannot change an id');
select throws_ok(
  $$update public.profiles set created_at = now() where id = 'b1000000-0000-0000-0000-00000000000f'$$,
  '42501', null, 'grant (-): an admin cannot change created_at');

select tests.authenticate_as('b1000000-0000-0000-0000-00000000000f');
select is(
  tests.exec_count($$update public.profiles set full_name = 'Nope' where id = 'b1000000-0000-0000-0000-00000000000d'$$),
  0::bigint, 'marketer update (-): a marketer updating another profile touches 0 rows');
select is(
  tests.exec_count($$update public.profiles set role = 'admin' where id = 'b1000000-0000-0000-0000-00000000000f'$$),
  0::bigint, 'marketer update (-): a marketer cannot promote himself (0 rows)');

select tests.authenticate_as('b1000000-0000-0000-0000-00000000000e');
select is(
  tests.exec_count($$update public.profiles set full_name = 'Nope' where id = 'b1000000-0000-0000-0000-00000000000d'$$),
  0::bigint, 'deactivated admin update (-): a deactivated admin touches 0 rows');

-- 3. Last active admin guard. Reduce the active admins to B only (owner role, models the service key path).
select tests.reset_role();
select lives_ok(
  $$update public.profiles set role = 'marketer' where id in ('b1000000-0000-0000-0000-00000000000a', 'b1000000-0000-0000-0000-00000000000c')$$,
  'guard (+): with three active admins, two can be demoted');
select throws_ok(
  $$update public.profiles set role = 'marketer', is_active = false where id = 'b1000000-0000-0000-0000-00000000000b'$$,
  'P0001', 'LAST_ADMIN', 'guard (-): demoting AND deactivating the only active admin in one statement is refused');
select lives_ok(
  $$update public.profiles set role = 'admin' where id = 'b1000000-0000-0000-0000-00000000000a'$$,
  'guard (+): promoting another profile is always allowed');

select tests.authenticate_as('b1000000-0000-0000-0000-00000000000a');
select is(
  tests.exec_count($$update public.profiles set role = 'marketer', is_active = false where id = 'b1000000-0000-0000-0000-00000000000b'$$),
  1::bigint, 'guard (+): admin A demotes and deactivates admin B in one statement because A stays an active admin');
select tests.reset_role();
select is(
  (select count(*)::int from public.profiles where role = 'admin' and is_active and id::text like 'b1000000-%'),
  1, 'after the sequence exactly one of our admins is active (the guard never let it reach zero)');

-- 7. log_audit(): the four user actions of phase 3
select tests.authenticate_as('b1000000-0000-0000-0000-00000000000a');
select lives_ok(
  format($$select public.log_audit(%L, 'user', 'p3-target', %L::jsonb)$$, a,
    case when a = 'user.role_changed'
      then '{"email": "p3-d@x.test", "from": "marketer", "to": "admin"}' else '{"email": "p3-d@x.test"}' end),
  'log_audit (+): admin writes ' || a)
from unnest(array['user.invited', 'user.role_changed', 'user.deactivated', 'user.reactivated']) as a;
select is(
  (select count(*)::int from public.audit_log
    where target_id = 'p3-target' and target_type = 'user'
      and actor_id = 'b1000000-0000-0000-0000-00000000000a'),
  4, 'log_audit (+): four lines recorded, actor_id is the calling admin');
select is(
  (select metadata from public.audit_log where target_id = 'p3-target' and action = 'user.role_changed'),
  '{"email": "p3-d@x.test", "from": "marketer", "to": "admin"}'::jsonb,
  'log_audit (+): the from/to metadata of a role change is kept as sent');

select tests.authenticate_as('b1000000-0000-0000-0000-00000000000f');
select throws_ok(
  $$select public.log_audit('user.invited', 'user', 'p3-denied', '{}'::jsonb)$$,
  'P0001', 'FORBIDDEN', 'log_audit (-): a marketer gets FORBIDDEN');
select tests.authenticate_as('b1000000-0000-0000-0000-00000000000e');
select throws_ok(
  $$select public.log_audit('user.invited', 'user', 'p3-denied', '{}'::jsonb)$$,
  'P0001', 'FORBIDDEN', 'log_audit (-): a deactivated admin gets FORBIDDEN');
select tests.reset_role();
select is((select count(*)::int from public.audit_log where target_id = 'p3-denied'), 0,
  'log_audit (-): refused calls left no line');

-- 8. Reading the log with the actor embed (PostgREST joins audit_log.actor_id -> profiles)
select tests.authenticate_as('b1000000-0000-0000-0000-00000000000a');
select is(
  (select p.full_name from public.audit_log l join public.profiles p on p.id = l.actor_id
    where l.target_id = 'p3-target' and l.action = 'user.invited'),
  'Phase3 Admin A', 'embed (+): an admin reads the audit line together with the actor full_name');
select is(
  (select count(*)::int from public.audit_log l join public.profiles p on p.id = l.actor_id
    where l.target_id = 'p3-target'),
  4, 'embed (+): all four lines join to their actor');
select tests.authenticate_as('b1000000-0000-0000-0000-00000000000f');
select is((select count(*)::int from public.audit_log where target_id = 'p3-target'), 0,
  'audit select (-): a marketer sees no audit line');
select tests.authenticate_as('b1000000-0000-0000-0000-00000000000e');
select is((select count(*)::int from public.audit_log where target_id = 'p3-target'), 0,
  'audit select (-): a deactivated admin sees no audit line');

-- 9. Keyset ordering contract: (created_at desc, id desc), ties on created_at broken by id, no gap or duplicate
select tests.reset_role();
insert into public.audit_log (action, target_type, target_id, created_at) values
  ('user.invited', 'user', 'ks-0', '2026-01-01 00:00:00+00'),
  ('user.invited', 'user', 'ks-1', '2026-01-02 00:00:00+00'),
  ('user.invited', 'user', 'ks-2', '2026-01-02 00:00:00+00'),
  ('user.invited', 'user', 'ks-3', '2026-01-02 00:00:00+00');
select tests.authenticate_as('b1000000-0000-0000-0000-00000000000a');
select is(
  (select array_agg(target_id order by created_at desc, id desc) from public.audit_log where target_id like 'ks-%'),
  array['ks-3', 'ks-2', 'ks-1', 'ks-0'],
  'keyset (+): rows sharing a created_at come back newest id first, older rows after');
select is(
  (select array_agg(target_id order by created_at desc, id desc) from
    (select * from public.audit_log where target_id like 'ks-%' order by created_at desc, id desc limit 2) as p1),
  array['ks-3', 'ks-2'], 'keyset (+): page 1 (limit 2) is ks-3, ks-2');
select is(
  (select array_agg(target_id order by created_at desc, id desc) from
    (select l.* from public.audit_log l,
        (select created_at as c, id as i from public.audit_log where target_id = 'ks-2') as cur
      where l.target_id like 'ks-%'
        and (l.created_at < cur.c or (l.created_at = cur.c and l.id < cur.i))
      order by l.created_at desc, l.id desc limit 2) as p2),
  array['ks-1', 'ks-0'],
  'keyset (+): page 2 after the cursor of ks-2 is ks-1, ks-0 (no gap, no duplicate, the tie is broken by id)');

select tests.reset_role();
select * from finish();
rollback;
