"""Billing table migrations for AutoPay and invoice enhancements."""

from __future__ import annotations

import logging

from sqlalchemy import Engine, inspect, text

logger = logging.getLogger(__name__)


def _add_column_if_missing(
    existing_columns: set[str],
    statements: list[str],
    column: str,
    ddl: str,
) -> None:
    if column not in existing_columns:
        statements.append(ddl)


def apply_billing_migrations(db_engine: Engine) -> None:
    """Add AutoPay / invoice columns when missing."""
    inspector = inspect(db_engine)
    table_names = set(inspector.get_table_names())
    statements: list[str] = []

    if "payment_transaction" in table_names:
        payment_columns = {
            column["name"] for column in inspector.get_columns("payment_transaction")
        }
        _add_column_if_missing(
            payment_columns,
            statements,
            "gateway_subscription_id",
            "ALTER TABLE payment_transaction "
            "ADD COLUMN gateway_subscription_id VARCHAR(100)",
        )
        _add_column_if_missing(
            payment_columns,
            statements,
            "gateway_customer_id",
            "ALTER TABLE payment_transaction "
            "ADD COLUMN gateway_customer_id VARCHAR(100)",
        )
        _add_column_if_missing(
            payment_columns,
            statements,
            "payment_type",
            "ALTER TABLE payment_transaction "
            "ADD COLUMN payment_type VARCHAR(20) NOT NULL DEFAULT 'one_time'",
        )
        _add_column_if_missing(
            payment_columns,
            statements,
            "retry_of_payment_id",
            "ALTER TABLE payment_transaction "
            "ADD COLUMN retry_of_payment_id INTEGER "
            "REFERENCES payment_transaction(id) ON DELETE SET NULL",
        )

    if "invoice" in table_names:
        invoice_columns = {
            column["name"] for column in inspector.get_columns("invoice")
        }
        _add_column_if_missing(
            invoice_columns,
            statements,
            "invoice_date",
            "ALTER TABLE invoice ADD COLUMN invoice_date TIMESTAMPTZ "
            "DEFAULT NOW() NOT NULL",
        )
        _add_column_if_missing(
            invoice_columns,
            statements,
            "billing_cycle",
            "ALTER TABLE invoice ADD COLUMN billing_cycle VARCHAR(20)",
        )
        _add_column_if_missing(
            invoice_columns,
            statements,
            "billing_city",
            "ALTER TABLE invoice ADD COLUMN billing_city VARCHAR(100)",
        )
        _add_column_if_missing(
            invoice_columns,
            statements,
            "company_name",
            "ALTER TABLE invoice ADD COLUMN company_name VARCHAR(255)",
        )
        _add_column_if_missing(
            invoice_columns,
            statements,
            "payment_method",
            "ALTER TABLE invoice ADD COLUMN payment_method VARCHAR(50)",
        )
        _add_column_if_missing(
            invoice_columns,
            statements,
            "payment_status",
            "ALTER TABLE invoice ADD COLUMN payment_status VARCHAR(20)",
        )

    if not statements:
        return

    with db_engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))

        payment_columns = (
            {
                column["name"]
                for column in inspector.get_columns("payment_transaction")
            }
            if "payment_transaction" in table_names
            else set()
        )
        # Re-inspect after adds is messy; create indexes with IF NOT EXISTS.
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_payment_transaction_gateway_subscription_id "
                "ON payment_transaction (gateway_subscription_id)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_payment_transaction_retry_of_payment_id "
                "ON payment_transaction (retry_of_payment_id)"
            )
        )

    logger.info("Applied %s billing migration statement(s)", len(statements))
