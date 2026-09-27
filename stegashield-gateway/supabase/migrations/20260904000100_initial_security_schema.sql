-- StegaShield core schema. All attribution writes are server-only so clients
-- cannot forge download or forensic records.
create extension if not exists pgcrypto;

create type public.app_role as enum ('user', 'admin');
create type public.document_format as enum ('docx', 'pdf');
create type public.forensic_outcome as enum ('matched', 'inconclusive');

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text check (display_name is null or char_length(display_name) between 1 and 120),
  role public.app_role not null default 'user',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  started_at timestamptz not null default now(),
  ended_at timestamptz,
  ip_address inet,
  user_agent text check (user_agent is null or char_length(user_agent) <= 512),
  check (ended_at is null or ended_at >= started_at)
);

create table public.documents (
  id uuid primary key default gen_random_uuid(),
  title text not null check (char_length(title) between 1 and 255),
  original_filename text not null check (char_length(original_filename) between 1 and 255),
  storage_path text not null unique check (storage_path !~ '(^|/)\.\.(/|$)'),
  format public.document_format not null,
  mime_type text not null,
  size_bytes bigint not null check (size_bytes > 0),
  sha256 text not null check (sha256 ~ '^[0-9a-f]{64}$'),
  uploaded_by uuid not null references public.profiles(id),
  created_at timestamptz not null default now(),
  archived_at timestamptz,
  check (
    (format = 'docx' and mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    or (format = 'pdf' and mime_type = 'application/pdf')
  )
);

create table public.document_permissions (
  document_id uuid not null references public.documents(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  granted_by uuid not null references public.profiles(id),
  granted_at timestamptz not null default now(),
  expires_at timestamptz,
  primary key (document_id, user_id),
  check (expires_at is null or expires_at > granted_at)
);

create table public.download_events (
  id uuid primary key default gen_random_uuid(),
  watermark_token uuid not null unique default gen_random_uuid(),
  document_id uuid not null references public.documents(id),
  user_id uuid not null references public.profiles(id),
  session_id uuid references public.sessions(id) on delete set null,
  downloaded_at timestamptz not null default now(),
  ip_address inet,
  user_agent text check (user_agent is null or char_length(user_agent) <= 512),
  unique (id, watermark_token)
);

create table public.forensic_events (
  id uuid primary key default gen_random_uuid(),
  performed_by uuid not null references public.profiles(id),
  watermark_token uuid,
  matched_download_id uuid,
  outcome public.forensic_outcome not null,
  valid_copies integer not null default 0 check (valid_copies >= 0),
  suspect_filename text check (suspect_filename is null or char_length(suspect_filename) <= 255),
  attempted_at timestamptz not null default now(),
  foreign key (matched_download_id, watermark_token)
    references public.download_events(id, watermark_token),
  check (
    (outcome = 'matched' and watermark_token is not null and matched_download_id is not null and valid_copies > 0)
    or (outcome = 'inconclusive' and matched_download_id is null)
  )
);

create index sessions_user_id_idx on public.sessions(user_id);
create index documents_uploaded_by_idx on public.documents(uploaded_by);
create index document_permissions_user_id_idx on public.document_permissions(user_id);
create index download_events_user_id_idx on public.download_events(user_id);
create index download_events_document_id_idx on public.download_events(document_id);
create index forensic_events_performed_by_idx on public.forensic_events(performed_by);
create index forensic_events_token_idx on public.forensic_events(watermark_token);

-- SECURITY DEFINER avoids recursive profile-policy evaluation. The locked
-- search_path and explicit schema names prevent object-shadowing attacks.
create function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.profiles
    where id = (select auth.uid()) and role = 'admin'
  );
$$;
revoke all on function public.is_admin() from public;
grant execute on function public.is_admin() to authenticated;

alter table public.profiles enable row level security;
alter table public.sessions enable row level security;
alter table public.documents enable row level security;
alter table public.document_permissions enable row level security;
alter table public.download_events enable row level security;
alter table public.forensic_events enable row level security;

create policy "profiles read self or admin" on public.profiles for select to authenticated
  using (id = (select auth.uid()) or (select public.is_admin()));

create policy "sessions read own or admin" on public.sessions for select to authenticated
  using (user_id = (select auth.uid()) or (select public.is_admin()));

create policy "documents read when permitted" on public.documents for select to authenticated
  using (
    (select public.is_admin()) or exists (
      select 1 from public.document_permissions p
      where p.document_id = documents.id
        and p.user_id = (select auth.uid())
        and (p.expires_at is null or p.expires_at > now())
    )
  );

create policy "permissions read own or admin" on public.document_permissions for select to authenticated
  using (user_id = (select auth.uid()) or (select public.is_admin()));

create policy "downloads read own or admin" on public.download_events for select to authenticated
  using (user_id = (select auth.uid()) or (select public.is_admin()));

create policy "forensics admin read" on public.forensic_events for select to authenticated
  using ((select public.is_admin()));

-- Administrative catalogue changes are allowed through RLS. Attribution and
-- forensic tables intentionally have no client write policies: the trusted API
-- service role must create these records before returning a protected file.
create policy "profiles admin update" on public.profiles for update to authenticated
  using ((select public.is_admin())) with check ((select public.is_admin()));
create policy "documents admin insert" on public.documents for insert to authenticated
  with check ((select public.is_admin()) and uploaded_by = (select auth.uid()));
create policy "documents admin update" on public.documents for update to authenticated
  using ((select public.is_admin())) with check ((select public.is_admin()));
create policy "documents admin delete" on public.documents for delete to authenticated
  using ((select public.is_admin()));
create policy "permissions admin insert" on public.document_permissions for insert to authenticated
  with check ((select public.is_admin()) and granted_by = (select auth.uid()));
create policy "permissions admin update" on public.document_permissions for update to authenticated
  using ((select public.is_admin())) with check ((select public.is_admin()));
create policy "permissions admin delete" on public.document_permissions for delete to authenticated
  using ((select public.is_admin()));

grant select on public.profiles, public.sessions, public.documents,
  public.document_permissions, public.download_events, public.forensic_events to authenticated;
grant insert, update, delete on public.documents, public.document_permissions to authenticated;
grant update on public.profiles to authenticated;

-- New accounts receive the least-privileged role. Role promotion remains a
-- trusted administrative operation.
create function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id, display_name, role)
  values (new.id, nullif(left(new.raw_user_meta_data ->> 'display_name', 120), ''), 'user');
  return new;
end;
$$;
revoke all on function public.handle_new_user() from public;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();
