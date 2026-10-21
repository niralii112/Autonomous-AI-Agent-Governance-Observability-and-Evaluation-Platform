"""append-only triggers

Blocks UPDATE and DELETE on the tables the spec marks IMMUTABLE (section 10.1):
actions, risk_assessments, governance_decisions, audit_events, evaluation_results.

Note: the file table in section 7.1 lists the first four; section 10.1 also lists
evaluation_results. We follow 10.1 (the stricter rule).

Revision ID: 0002
Revises: 0001
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

IMMUTABLE_TABLES = [
    "actions",
    "risk_assessments",
    "governance_decisions",
    "audit_events",
    "evaluation_results",
]


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION forbid_update_delete() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION '% is append-only: % is not allowed', TG_TABLE_NAME, TG_OP
                USING ERRCODE = 'integrity_constraint_violation';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for table in IMMUTABLE_TABLES:
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_append_only
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION forbid_update_delete();
            """
        )


def downgrade() -> None:
    for table in IMMUTABLE_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only ON {table}")
    op.execute("DROP FUNCTION IF EXISTS forbid_update_delete()")
