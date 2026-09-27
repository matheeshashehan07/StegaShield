begin;
create extension if not exists pgtap with schema extensions;
select plan(10);
insert into auth.users(id,raw_user_meta_data) values
('12000000-0000-4000-8000-000000000001','{}'),
('12000000-0000-4000-8000-000000000002','{}');
update public.profiles set role='admin' where id='12000000-0000-4000-8000-000000000002';
insert into public.job_positions(id,name) values ('52000000-0000-4000-8000-000000000001','Manager');
insert into public.position_memberships values ('12000000-0000-4000-8000-000000000001','52000000-0000-4000-8000-000000000001');
insert into public.documents(id,title,original_filename,storage_path,format,mime_type,size_bytes,sha256,uploaded_by)
values ('22000000-0000-4000-8000-000000000001','position fixture','original.pdf','position-fixture/original.pdf','pdf','application/pdf',100,repeat('a',64),'12000000-0000-4000-8000-000000000002');
insert into public.document_position_permissions(document_id,position_id,granted_by) values
('22000000-0000-4000-8000-000000000001','52000000-0000-4000-8000-000000000001','12000000-0000-4000-8000-000000000002');
set local role authenticated;
select set_config('request.jwt.claim.sub','12000000-0000-4000-8000-000000000001',true);
select is((select count(*)::integer from public.documents),1,'position member sees document');
select is(public.has_position_access('22000000-0000-4000-8000-000000000001'),true,'caller-scoped position access');
select throws_ok($$insert into public.job_positions(name) values ('Forged')$$,'42501',null,'member cannot create positions');
select throws_ok($$insert into public.position_memberships values ('12000000-0000-4000-8000-000000000002','52000000-0000-4000-8000-000000000001')$$,'42501',null,'member cannot assign positions');
select is((select count(*)::integer from public.position_memberships),0,'membership directory admin only');
reset role;
set local role service_role;
select lives_ok($$select public.record_download('12000000-0000-4000-8000-000000000001','22000000-0000-4000-8000-000000000001',gen_random_uuid(),repeat('b',64))$$,'position permits committed download');
reset role;
delete from public.position_memberships;
set local role authenticated;
select is((select count(*)::integer from public.documents),0,'removed membership removes visibility');
reset role;
set local role service_role;
select throws_ok($$select public.record_download('12000000-0000-4000-8000-000000000001','22000000-0000-4000-8000-000000000001',gen_random_uuid(),repeat('b',64))$$,'42501','Access denied','removed membership rejected at commit');
reset role;
insert into public.document_permissions(document_id,user_id,granted_by) values ('22000000-0000-4000-8000-000000000001','12000000-0000-4000-8000-000000000001','12000000-0000-4000-8000-000000000002');
set local role service_role;
select lives_ok($$select public.record_download('12000000-0000-4000-8000-000000000001','22000000-0000-4000-8000-000000000001',gen_random_uuid(),repeat('b',64))$$,'independent member grant still works');
reset role;
select is((select count(*)::integer from public.download_events),2,'failed position download creates no event');
select * from finish();
rollback;
