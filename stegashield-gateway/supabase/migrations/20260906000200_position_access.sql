-- Position memberships are trusted admin-managed data, never JWT metadata.
create table public.job_positions (
 id uuid primary key default gen_random_uuid(),
 name text not null unique check (char_length(btrim(name)) between 1 and 120)
);
create table public.position_memberships (
 user_id uuid primary key references public.profiles(id) on delete cascade,
 position_id uuid not null references public.job_positions(id) on delete cascade
);
create index position_memberships_position_idx on public.position_memberships(position_id);
create table public.document_position_permissions (
 document_id uuid not null references public.documents(id) on delete cascade,
 position_id uuid not null references public.job_positions(id) on delete cascade,
 granted_by uuid not null references public.profiles(id),
 granted_at timestamptz not null default now(),
 primary key(document_id,position_id)
);
alter table public.job_positions enable row level security;
alter table public.position_memberships enable row level security;
alter table public.document_position_permissions enable row level security;
revoke all on public.job_positions, public.position_memberships, public.document_position_permissions from anon, authenticated;
grant select,insert,update,delete on public.job_positions, public.position_memberships, public.document_position_permissions to authenticated;
grant select on public.position_memberships, public.document_position_permissions to service_role;
create policy "positions admin" on public.job_positions for all to authenticated
 using ((select public.is_admin())) with check ((select public.is_admin()));
create policy "memberships admin" on public.position_memberships for all to authenticated
 using ((select public.is_admin())) with check ((select public.is_admin()));
create policy "position grants admin read" on public.document_position_permissions for select to authenticated using ((select public.is_admin()));
create policy "position grants admin insert" on public.document_position_permissions for insert to authenticated with check ((select public.is_admin()) and granted_by=(select auth.uid()));
create policy "position grants admin delete" on public.document_position_permissions for delete to authenticated using ((select public.is_admin()));
create function public.has_position_access(p_document_id uuid) returns boolean
language sql stable security definer set search_path='' as $$
 select exists(select 1 from public.position_memberships m
 join public.document_position_permissions p on p.position_id=m.position_id
 where m.user_id=(select auth.uid()) and p.document_id=p_document_id);
$$;
revoke all on function public.has_position_access(uuid) from public,anon;
grant execute on function public.has_position_access(uuid) to authenticated;
create policy "documents position read" on public.documents for select to authenticated
 using (public.has_position_access(id));
create or replace function public.record_download(
  p_user_id uuid, p_document_id uuid, p_token uuid, p_sha256 text,
  p_ip inet default null, p_user_agent text default null, p_session_id uuid default null
) returns uuid language plpgsql security definer set search_path = '' as $$
declare
  app_role public.app_role;
  event_id uuid;
begin
  select role into app_role from public.profiles where id = p_user_id for share;
  if app_role is null then
    raise exception 'Access denied' using errcode = '42501';
  end if;
  perform 1 from public.documents where id = p_document_id and archived_at is null and format in ('docx', 'pdf') for share;
  if not found then
    raise exception 'Access denied' using errcode = '42501';
  end if;
  if app_role <> 'admin' then
    perform 1 from public.document_permissions
      where document_id = p_document_id and user_id = p_user_id
      and (expires_at is null or expires_at > clock_timestamp()) for share;
    if not found then
      perform 1 from public.position_memberships m
        join public.document_position_permissions p on p.position_id=m.position_id
        where m.user_id=p_user_id and p.document_id=p_document_id
        for share of m,p;
      if not found then
        raise exception 'Access denied' using errcode = '42501';
      end if;
    end if;
  end if;
  if p_sha256 is null then
    raise exception 'Protected digest required' using errcode = '23514';
  end if;
  if p_session_id is not null then
    insert into public.sessions(id,user_id,ip_address,user_agent)
      values (p_session_id,p_user_id,p_ip,left(p_user_agent,512)) on conflict (id) do nothing;
    perform 1 from public.sessions where id=p_session_id and user_id=p_user_id and ended_at is null for share;
    if not found then
      raise exception 'Access denied' using errcode = '42501';
    end if;
  end if;
  insert into public.download_events (watermark_token, document_id, user_id, protected_sha256, ip_address, user_agent, session_id)
    values (p_token, p_document_id, p_user_id, p_sha256, p_ip, left(p_user_agent, 512), p_session_id)
    returning id into event_id;
  return event_id;
end;
$$;
revoke all on function public.record_download(uuid, uuid, uuid, text, inet, text, uuid) from public, anon, authenticated;
grant execute on function public.record_download(uuid, uuid, uuid, text, inet, text, uuid) to service_role;
