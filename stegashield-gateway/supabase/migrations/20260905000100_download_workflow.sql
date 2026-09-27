-- Originals must never be available through client Storage credentials.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('stegashield-originals', 'stegashield-originals', false, 10485760,
  array['application/vnd.openxmlformats-officedocument.wordprocessingml.document']);
-- Restrictive policies prevent unrelated permissive policies opening this bucket.
create policy "gateway originals server only" on storage.objects as restrictive
for all to anon, authenticated
using (bucket_id <> 'stegashield-originals')
with check (bucket_id <> 'stegashield-originals');

alter table public.download_events add column protected_sha256 text
  check (protected_sha256 ~ '^[0-9a-f]{64}$');
alter table public.forensic_events add column reason text;
alter table public.forensic_events add column attempt_id uuid not null default gen_random_uuid();
alter table public.forensic_events add column completed boolean not null default true;
create index forensic_events_attempt_idx on public.forensic_events(attempt_id);

-- Explicit privileges, independent of Supabase project default grants.
revoke all on public.download_events, public.forensic_events, public.sessions from anon, authenticated;
grant select on public.sessions to authenticated;
-- Token-to-user mappings are forensic information, including a user's own mapping.
grant select on public.download_events, public.forensic_events to authenticated;
drop policy "downloads read own or admin" on public.download_events;
create policy "downloads admin read" on public.download_events for select to authenticated
using ((select public.is_admin()));
grant select, insert on public.download_events, public.forensic_events to service_role;
revoke update, delete, truncate on public.download_events, public.forensic_events from service_role;
grant select, insert, update, delete on public.documents, public.document_permissions to service_role;
grant select on public.profiles to service_role;
grant select, insert on public.sessions to service_role;

-- Historic identity mappings and original metadata are immutable. Replace a
-- document by uploading a new document ID; archive its old metadata instead.
create function public.guard_document_original() returns trigger language plpgsql
set search_path = '' as $$
begin
  if (new.storage_path, new.sha256, new.size_bytes, new.format, new.mime_type, new.uploaded_by)
     is distinct from
     (old.storage_path, old.sha256, old.size_bytes, old.format, old.mime_type, old.uploaded_by) then
    raise exception 'Original document metadata is immutable' using errcode = '23514';
  end if;
  return new;
end;
$$;
create trigger immutable_document_original before update on public.documents
for each row execute function public.guard_document_original();
revoke all on function public.guard_document_original() from public;

create function public.reject_audit_mutation() returns trigger language plpgsql
set search_path = '' as $$
begin
  raise exception 'Audit records are append only' using errcode = '23514';
end;
$$;
create trigger immutable_download_event before update or delete on public.download_events
for each row execute function public.reject_audit_mutation();
create trigger immutable_forensic_event before update or delete on public.forensic_events
for each row execute function public.reject_audit_mutation();
revoke all on function public.reject_audit_mutation() from public;

-- Only the API may supply the verified principal and freshly generated token.
-- Recheck authorization at the point of recording, under row locks, so a revoked
-- permission or archived document cannot be accepted from a stale API read.
create function public.record_download(
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
  perform 1 from public.documents where id = p_document_id and archived_at is null and format = 'docx' for share;
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
