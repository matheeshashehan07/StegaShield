-- Small normalised avatars are stored privately with RLS, not public object URLs.
create table public.profile_photos (
 user_id uuid primary key references public.profiles(id) on delete cascade,
 image_base64 text not null check (octet_length(image_base64) <= 140000),
 updated_at timestamptz not null default now()
);
alter table public.profile_photos enable row level security;
revoke all on public.profile_photos from anon, authenticated;
grant select on public.profile_photos to authenticated;
create policy "photos read self or admin" on public.profile_photos for select to authenticated
 using (user_id=(select auth.uid()) or (select public.is_admin()));

-- Only the validated API may supply normalised JPEG bytes and the verified user.
-- No role, email, membership, or other account fields can be changed here.
create function public.update_profile_details(p_user_id uuid, p_display_name text,
 p_change_photo boolean default false, p_image_base64 text default null)
returns boolean language plpgsql security definer set search_path='' as $$
begin
 if p_display_name is null or char_length(btrim(p_display_name)) not between 1 and 120 then
   raise exception 'Invalid display name' using errcode='23514';
 end if;
 update public.profiles set display_name=btrim(p_display_name), updated_at=now() where id=p_user_id;
 if not found then raise exception 'Profile unavailable' using errcode='42501'; end if;
 if p_change_photo then
   if p_image_base64 is null then
     delete from public.profile_photos where user_id=p_user_id;
   else
     insert into public.profile_photos(user_id,image_base64) values(p_user_id,p_image_base64)
     on conflict(user_id) do update set image_base64=excluded.image_base64,updated_at=now();
   end if;
 end if;
 return true;
end;
$$;
revoke all on function public.update_profile_details(uuid,text,boolean,text) from public,anon,authenticated;
grant execute on function public.update_profile_details(uuid,text,boolean,text) to service_role;
