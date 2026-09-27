begin;
create extension if not exists pgtap with schema extensions;
select plan(7);
insert into auth.users(id,raw_user_meta_data) values
('13000000-0000-4000-8000-000000000001','{}'),
('13000000-0000-4000-8000-000000000002','{}');
set local role authenticated;
select set_config('request.jwt.claim.sub','13000000-0000-4000-8000-000000000001',true);
select throws_ok($$select public.update_profile_details('13000000-0000-4000-8000-000000000002','Forged',true,'/9j/')$$,'42501',null,'clients cannot invoke trusted profile update');
select throws_ok($$insert into public.profile_photos(user_id,image_base64) values('13000000-0000-4000-8000-000000000001','/9j/')$$,'42501',null,'raw photo writes blocked');
reset role;
set local role service_role;
select lives_ok($$select public.update_profile_details('13000000-0000-4000-8000-000000000001','Alice',true,'/9j/')$$,'validated API can atomically update name and photo');
reset role;
set local role authenticated;
select is((select display_name from public.profiles where id=auth.uid()),'Alice','new name visible');
select is((select role::text from public.profiles where id=auth.uid()),'user','role unchanged');
select is((select count(*)::integer from public.profile_photos),1,'own picture readable');
select set_config('request.jwt.claim.sub','13000000-0000-4000-8000-000000000002',true);
select is((select count(*)::integer from public.profile_photos),0,'other member picture private');
reset role;
select * from finish();
rollback;
