begin;
create extension if not exists pgtap with schema extensions;
select plan(5);
insert into auth.users(id, raw_user_meta_data) values
('11000000-0000-4000-8000-000000000001','{}'),
('11000000-0000-4000-8000-000000000002','{}');
update public.profiles set role='admin' where id in ('11000000-0000-4000-8000-000000000001','11000000-0000-4000-8000-000000000002');
insert into public.documents(id,title,original_filename,storage_path,format,mime_type,size_bytes,sha256,uploaded_by)
values ('21000000-0000-4000-8000-000000000001','session fixture','original.docx','session-fixture/original.docx','docx',
'application/vnd.openxmlformats-officedocument.wordprocessingml.document',100,repeat('a',64),'11000000-0000-4000-8000-000000000001');
set local role service_role;
select lives_ok($$select public.record_download('11000000-0000-4000-8000-000000000001','21000000-0000-4000-8000-000000000001',gen_random_uuid(),repeat('b',64),null,null,'41000000-0000-4000-8000-000000000001')$$,
'verified session is registered with download');
select is((select user_id::text from public.sessions where id='41000000-0000-4000-8000-000000000001'), '11000000-0000-4000-8000-000000000001','session belongs to principal');
select is((select session_id::text from public.download_events where document_id='21000000-0000-4000-8000-000000000001'), '41000000-0000-4000-8000-000000000001','download references session');
select throws_ok($$select public.record_download('11000000-0000-4000-8000-000000000002','21000000-0000-4000-8000-000000000001',gen_random_uuid(),repeat('b',64),null,null,'41000000-0000-4000-8000-000000000001')$$,
'42501', 'Access denied', 'another user cannot reuse session');
reset role;
update public.sessions set ended_at=now() where id='41000000-0000-4000-8000-000000000001';
set local role service_role;
select throws_ok($$select public.record_download('11000000-0000-4000-8000-000000000001','21000000-0000-4000-8000-000000000001',gen_random_uuid(),repeat('b',64),null,null,'41000000-0000-4000-8000-000000000001')$$,
'42501', 'Access denied', 'ended session cannot issue more downloads');
reset role;
select * from finish();
rollback;
