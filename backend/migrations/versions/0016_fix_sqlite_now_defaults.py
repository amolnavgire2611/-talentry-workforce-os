"""Repair SQLite column defaults that use the PostgreSQL-only now() function.

Revision ID: 0016_fix_sqlite_now_defaults
Revises: 0015_merge_module_permissions
Create Date: 2026-10-18

Revisions 0009-0014 created timestamp columns with ``server_default=sa.text("now()")``.
PostgreSQL accepts ``now()``, but SQLite only implements ``CURRENT_TIMESTAMP``.
On SQLite every INSERT that relies on those defaults fails with
``sqlite3.OperationalError: unknown function: now()`` (observed on
``GET /api/my-permissions`` while seeding the module catalog after login).

SQLite cannot ALTER a column default, so each affected table is rebuilt:
the stored CREATE TABLE text is rewritten, rows are copied, the old table is
dropped, the replacement is renamed into place, and explicit indexes are
recreated. Revisions 0009-0014 are left untouched; this forward migration
repairs both existing databases and databases created by the full chain.

On non-SQLite dialects this is a no-op because now() is valid there.
"""

import re

from alembic import op

# revision identifiers, used by Alembic.
revision = "0016_fix_sqlite_now_defaults"
down_revision = "0015_merge_module_permissions"
branch_labels = None
depends_on = None

_DEFAULT_NOW = ("DEFAULT (now())", "DEFAULT now()")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        return

    broken_tables = bind.exec_driver_sql(
        "SELECT name, sql FROM sqlite_master "
        "WHERE type='table' AND sql LIKE '%now()%'"
    ).fetchall()

    for name, sql in broken_tables:
        fixed = sql
        for pattern in _DEFAULT_NOW:
            fixed = fixed.replace(pattern, "DEFAULT CURRENT_TIMESTAMP")
        if fixed == sql:
            # now() appears in an unexpected position; leave the table untouched
            # rather than rebuild it with an unmodified definition.
            continue

        indexes = bind.exec_driver_sql(
            "SELECT sql FROM sqlite_master "
            "WHERE type='index' AND tbl_name = ? AND sql IS NOT NULL",
            (name,),
        ).scalars().all()

        temp_name = f"{name}_0016_fix"
        create_temp = re.sub(
            r'^CREATE TABLE\s+(IF NOT EXISTS\s+)?"?%s"?' % re.escape(name),
            'CREATE TABLE "%s"' % temp_name,
            fixed,
            count=1,
            flags=re.IGNORECASE,
        )
        if create_temp == fixed:
            raise RuntimeError(
                f"0016 could not rewrite the CREATE TABLE statement for {name!r}"
            )

        bind.exec_driver_sql(f'DROP TABLE IF EXISTS "{temp_name}"')
        bind.exec_driver_sql(create_temp)
        bind.exec_driver_sql(
            'INSERT INTO "%s" SELECT * FROM "%s"' % (temp_name, name)
        )
        bind.exec_driver_sql(f'DROP TABLE "{name}"')
        bind.exec_driver_sql(
            'ALTER TABLE "%s" RENAME TO "%s"' % (temp_name, name)
        )
        # Recreate explicit indexes after the rename: their SQL references the
        # original table name and the names were freed when the old table dropped.
        for index_sql in indexes:
            bind.exec_driver_sql(index_sql)


def downgrade() -> None:
    # Forward-only repair: re-introducing now() defaults would break SQLite
    # inserts again, so this migration is intentionally irreversible.
    pass
