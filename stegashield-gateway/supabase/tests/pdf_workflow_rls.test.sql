-- Runs inside a transaction; all fixtures and privilege changes roll back.
begin;
create extension if not exists pgtap with schema extensions;
select plan(25);

insert into auth.users (id, raw_user_meta_data) values
 ('10000000-0000-4000-8000-000000000001', '{}'),
 ('10000000-0000-4000-8000-000000000002', '{}'),
 ('10000000-0000-4000-8000-000000000003', '{"role":"admin"}');
select is((select role::text from public.profiles where id='10000000-0000-4000-8000-000000000003'), 'user', 'metadata cannot promote account');
update public.profiles set role='admin' where id='10000000-0000-4000-8000-000000000003';
insert into public.documents (id,title,original_filename,storage_path,format,mime_type,size_bytes,sha256,uploaded_by)
values ('20000000-0000-4000-8000-000000000001','fixture','original.pdf','20000000-0000-4000-8000-000000000001/original.pdf','pdf',
'application/pdf',100,repeat('a',64),'10000000-0000-4000-8000-000000000003');
insert into public.document_permissions(document_id,user_id,granted_by) values
 ('20000000-0000-4000-8000-000000000001','10000000-0000-4000-8000-000000000001','10000000-0000-4000-8000-000000000003');
insert into public.forensic_events(performed_by,outcome,reason)
values ('10000000-0000-4000-8000-000000000003','inconclusive','test_fixture');

set local role authenticated;
select set_config('request.jwt.claim.sub', '10000000-0000-4000-8000-000000000001', true);
select is((select count(*)::integer from public.documents), 1, 'permitted user sees document');
select is((select count(*)::integer from public.profiles), 1, 'user sees only own profile');
select is((select count(*)::integer from public.forensic_events), 0, 'user cannot see forensics');
select throws_ok($$insert into public.forensic_events(performed_by,outcome) values ('10000000-0000-4000-8000-000000000001','inconclusive')$$,
'42501', null, 'client cannot forge forensic records');
select throws_ok($$select public.record_download('10000000-0000-4000-8000-000000000001','20000000-0000-4000-8000-000000000001',gen_random_uuid(),repeat('b',64))$$,
'42501', null, 'client cannot call trusted RPC');
select throws_ok($$insert into public.download_events(document_id,user_id) values ('20000000-0000-4000-8000-000000000001','10000000-0000-4000-8000-000000000001')$$,
'42501', null, 'client cannot forge a download');
update public.profiles set role='admin' where id='10000000-0000-4000-8000-000000000001';
select is((select role::text from public.profiles where id=auth.uid()), 'user', 'self promotion blocked');
select set_config('request.jwt.claim.sub', '10000000-0000-4000-8000-000000000002', true);
select is((select count(*)::integer from public.documents), 0, 'other user cannot see document');

reset role;
set local role service_role;
select lives_ok($$select public.record_download('10000000-0000-4000-8000-000000000001','20000000-0000-4000-8000-000000000001','30000000-0000-4000-8000-000000000001',repeat('b',64))$$, 'server records allowed download');
select throws_ok($$select public.record_download('10000000-0000-4000-8000-000000000002','20000000-0000-4000-8000-000000000001',gen_random_uuid(),repeat('b',64))$$,
'42501', 'Access denied', 'server RPC still rejects unpermitted users');
select throws_ok($$select public.record_download('10000000-0000-4000-8000-000000000001','20000000-0000-4000-8000-000000000001','30000000-0000-4000-8000-000000000001',repeat('b',64))$$,
'23505', null, 'duplicate token rejected');

reset role;
update public.document_permissions set granted_at=now()-interval '2 days',expires_at=now()-interval '1 day';
set local role service_role;
select throws_ok($$select public.record_download('10000000-0000-4000-8000-000000000001','20000000-0000-4000-8000-000000000001',gen_random_uuid(),repeat('b',64))$$,
'42501', 'Access denied', 'expired permission rejected at commit');
reset role;
update public.documents set archived_at=now();
set local role service_role;
select throws_ok($$select public.record_download('10000000-0000-4000-8000-000000000003','20000000-0000-4000-8000-000000000001',gen_random_uuid(),repeat('b',64))$$,
'42501', 'Access denied', 'archived documents rejected even for admin');
reset role;
select throws_ok($$update public.documents set sha256=repeat('c',64)$$, '23514', 'Original document metadata is immutable', 'original metadata immutable');
select throws_ok($$update public.download_events set user_id='10000000-0000-4000-8000-000000000002'$$,
'23514', 'Audit records are append only', 'historic mapping immutable');
select throws_ok($$insert into public.forensic_events(performed_by,watermark_token,matched_download_id,outcome,valid_copies)
select '10000000-0000-4000-8000-000000000003',gen_random_uuid(),id,'matched',1 from public.download_events$$,
'23503', null, 'forensic token must match referenced event');

set local role authenticated;
select set_config('request.jwt.claim.sub', '10000000-0000-4000-8000-000000000001', true);
select is((select count(*)::integer from public.download_events), 0, 'ordinary users cannot query token mappings');
select set_config('request.jwt.claim.sub', '10000000-0000-4000-8000-000000000003', true);
select is((select count(*)::integer from public.download_events), 1, 'admin can query token mappings');
select is((select count(*)::integer from public.forensic_events), 1, 'admin can see forensic audit');
reset role;
select is((select public from storage.buckets where id='stegashield-originals'), false, 'original bucket private');
-- Simulate an unrelated permissive Storage policy; restrictive guard still wins.
insert into storage.objects(bucket_id,name) values ('stegashield-originals','fixture.pdf');
create policy test_broad_storage_read on storage.objects for select to authenticated using (true);
set local role authenticated;
select is((select count(*)::integer from storage.objects where bucket_id='stegashield-originals'), 0, 'even admin JWT cannot fetch original directly');
select set_config('request.jwt.claim.sub', '10000000-0000-4000-8000-000000000001', true);
select is((select count(*)::integer from storage.objects where bucket_id='stegashield-originals'), 0, 'ordinary JWT cannot fetch original directly');
reset role;
set local role anon;
select throws_ok($$select public.record_download('10000000-0000-4000-8000-000000000001','20000000-0000-4000-8000-000000000001',gen_random_uuid(),repeat('b',64))$$,
'42501', null, 'anonymous RPC denied');
reset role;
select is((select count(*)::integer from public.download_events), 1, 'failed operations created no download records');
select * from finish();
rollback;
