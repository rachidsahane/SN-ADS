-- Migration 1: the nine enumerated types (DATA_MODEL 3). Labels AND their order are part of the contract.
begin;
\ir _helpers.psql
select plan(18);

select has_enum('public', 'app_role', 'type public.app_role exists');
select enum_has_labels('public', 'app_role', array['marketer', 'admin'], 'app_role labels, in order');

select has_enum('public', 'gender', 'type public.gender exists');
select enum_has_labels('public', 'gender', array['Male', 'Female'], 'gender labels, in order');

select has_enum('public', 'campaign_channel', 'type public.campaign_channel exists');
select enum_has_labels('public', 'campaign_channel',
  array['Social Media', 'Email', 'PPC', 'SEO', 'Referral'], 'campaign_channel labels, in order');

select has_enum('public', 'campaign_type', 'type public.campaign_type exists');
select enum_has_labels('public', 'campaign_type',
  array['Awareness', 'Consideration', 'Conversion', 'Retention'], 'campaign_type labels, in order');

select has_enum('public', 'dataset_source', 'type public.dataset_source exists');
select enum_has_labels('public', 'dataset_source', array['seed', 'agency'], 'dataset_source labels, in order');

select has_enum('public', 'upload_status', 'type public.upload_status exists');
select enum_has_labels('public', 'upload_status',
  array['importing', 'ready', 'failed'], 'upload_status labels, in order');

select has_enum('public', 'training_status', 'type public.training_status exists');
select enum_has_labels('public', 'training_status',
  array['queued', 'running', 'succeeded', 'failed'], 'training_status labels, in order');

select has_enum('public', 'data_scope', 'type public.data_scope exists');
select enum_has_labels('public', 'data_scope', array['all', 'agency_only'], 'data_scope labels, in order');

select has_enum('public', 'performance_level', 'type public.performance_level exists');
select enum_has_labels('public', 'performance_level',
  array['low', 'medium', 'high'], 'performance_level labels, in order');

select * from finish();
rollback;
