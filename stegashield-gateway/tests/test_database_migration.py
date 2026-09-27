import re
from pathlib import Path


MIGRATION = next((Path(__file__).parents[1] / "supabase" / "migrations").glob("*_initial_security_schema.sql"))
SQL = MIGRATION.read_text(encoding="utf-8").lower()
TABLES = (
    "profiles",
    "sessions",
    "documents",
    "document_permissions",
    "download_events",
    "forensic_events",
)


def test_every_security_table_enables_rls() -> None:
    for table in TABLES:
        assert f"alter table public.{table} enable row level security" in SQL


def test_attribution_tables_have_no_authenticated_write_policy_or_grant() -> None:
    for table in ("download_events", "forensic_events"):
        assert not re.search(
            rf'create policy .* on public\.{table} for (insert|update|delete|all)', SQL
        )
        assert not re.search(rf"grant (insert|update|delete|all).*public\.{table}", SQL)


def test_forensic_records_are_admin_read_only() -> None:
    policy = re.search(
        r'create policy "forensics admin read".*?;', SQL, flags=re.DOTALL
    )
    assert policy is not None
    assert "is_admin()" in policy.group(0)
    assert "auth.uid()" not in policy.group(0)


def test_download_token_is_random_and_unique_per_event() -> None:
    table = re.search(r"create table public\.download_events \((.*?)\n\);", SQL, re.DOTALL)
    assert table is not None
    token_column = re.search(r"watermark_token[^\n]+", table.group(1))
    assert token_column is not None
    assert "unique" in token_column.group(0)
    assert "default gen_random_uuid()" in token_column.group(0)


def test_forensic_match_must_reference_the_same_download_and_token() -> None:
    table = re.search(r"create table public\.forensic_events \((.*?)\n\);", SQL, re.DOTALL)
    assert table is not None
    normalized = " ".join(table.group(1).split())
    assert "foreign key (matched_download_id, watermark_token)" in normalized
    assert "references public.download_events(id, watermark_token)" in normalized


def test_admin_helper_has_locked_search_path() -> None:
    function = re.search(r"create function public\.is_admin\(\).*?\$\$;", SQL, re.DOTALL)
    assert function is not None
    assert "security definer" in function.group(0)
    assert "set search_path = ''" in function.group(0)
