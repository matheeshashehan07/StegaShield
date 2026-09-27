-- Extend formats only; original access policies and transactional checks stay intact.
update storage.buckets set allowed_mime_types = array[
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/pdf'
] where id = 'stegashield-originals';

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
      raise exception 'Access denied' using errcode = '42501';
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
