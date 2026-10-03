-- Global guarantees on schema public, valid for every table and function of every phase (this file grows
-- by itself as phases 4, 6 and 14 add tables): forced RLS everywhere, nothing for anon, hardened default
-- privileges, security definer functions pinned to an empty search_path (DATA_MODEL 6, SECURITY_NOTES 3.7).
begin;
\ir _helpers.psql
select plan(13);

-- (a) every table of public: RLS enabled AND forced
select cmp_ok(
  (select count(*)::int from pg_class c
    where c.relkind in ('r', 'p') and c.relnamespace = 'public'::regnamespace),
  '>=', 2, '(a) public holds at least the tables of migrations 1 and 2 (the check below is not vacuous)');
select is(
  (select array_agg(c.relname::text order by c.relname) from pg_class c
    where c.relkind in ('r', 'p') and c.relnamespace = 'public'::regnamespace
      and not (c.relrowsecurity and c.relforcerowsecurity)),
  null, '(a) every table of public has RLS enabled AND forced (no exception listed)');

-- (b) anon holds nothing on any table, column or sequence of public
select is(
  (select count(*)::int from pg_class c
    where c.relnamespace = 'public'::regnamespace and c.relkind in ('r', 'p', 'v', 'm', 'f')
      and has_table_privilege('anon', c.oid, 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')),
  0, '(b) anon has no table privilege on any relation of public');
select is(
  (select count(*)::int from pg_class c
    where c.relnamespace = 'public'::regnamespace and c.relkind in ('r', 'p', 'v', 'm', 'f')
      and has_any_column_privilege('anon', c.oid, 'SELECT,INSERT,UPDATE,REFERENCES')),
  0, '(b) anon has no column privilege on any relation of public');
select is(
  (select count(*)::int from pg_class c
    where c.relnamespace = 'public'::regnamespace and c.relkind = 'S'
      and case when c.relkind = 'S' then has_sequence_privilege('anon', c.oid, 'USAGE,SELECT,UPDATE') else false end),
  0, '(b) anon has no privilege on any sequence of public');
select is(
  (select count(*)::int from information_schema.role_table_grants
    where table_schema = 'public' and grantee = 'anon'),
  0, '(b) information_schema lists no grant to anon on public tables');

-- (d) premise of the architecture: the role owning the security definer functions bypasses RLS
select is((select rolbypassrls from pg_roles where rolname = 'postgres'), true,
  '(d) postgres (owner of the security definer functions and of the tables) has BYPASSRLS');

-- (e) every security definer function of public pins an empty search_path
select cmp_ok(
  (select count(*)::int from pg_proc p
    where p.pronamespace = 'public'::regnamespace and p.prosecdef
      and not exists (select 1 from pg_depend d where d.objid = p.oid and d.deptype = 'e')),
  '>=', 6, '(e) public holds the security definer functions of migrations 1 and 2 (the check below is not vacuous)');
select is(
  (select array_agg(p.oid::regprocedure::text order by p.oid::regprocedure::text) from pg_proc p
    where p.pronamespace = 'public'::regnamespace and p.prosecdef
      and not exists (select 1 from pg_depend d where d.objid = p.oid and d.deptype = 'e')
      and not coalesce(p.proconfig, '{}'::text[]) @> array['search_path=""']),
  null, '(e) every security definer function of public has search_path = ""');

-- (f) the only function of public that anon may execute is schema_version()
select is(
  (select array_agg(p.proname::text order by p.proname::text) from pg_proc p
    where p.pronamespace = 'public'::regnamespace
      and not exists (select 1 from pg_depend d where d.objid = p.oid and d.deptype = 'e')
      and has_function_privilege('anon', p.oid, 'EXECUTE')),
  array['schema_version'], '(f) anon can execute schema_version() and no other function of public');

-- (c) hardened default privileges: objects created later in public are closed to anon
create table public._probe_table (id integer);
create sequence public._probe_sequence;
create function public._probe_fn() returns integer language sql as 'select 1';
select is(
  has_table_privilege('anon', 'public._probe_table', 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'),
  false, '(c) a table created later in public is closed to anon');
select is(
  has_sequence_privilege('anon', 'public._probe_sequence', 'USAGE,SELECT,UPDATE'),
  false, '(c) a sequence created later in public is closed to anon');
select is(
  has_function_privilege('anon', 'public._probe_fn()', 'EXECUTE'),
  false, '(c) a function created later in public cannot be executed by anon');

select * from finish();
rollback;
