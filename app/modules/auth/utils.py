import logging
import os
import random
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import bcrypt
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

OTP_EXPIRY_MINUTES = 10


def _get_smtp_settings() -> dict[str, str | int]:
    """Read SMTP configuration from environment variables at send time."""
    smtp_user = os.getenv("SMTP_USER", "")
    return {
        "host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "user": smtp_user,
        "password": os.getenv("SMTP_PASSWORD", "").replace(" ", ""),
        "from_email": os.getenv("SMTP_FROM", smtp_user),
    }


def hash_password(password: str) -> str:
    """Return a bcrypt hash for the given plain-text password."""
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a stored bcrypt hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def generate_verification_code() -> str:
    """Generate a random 6-digit numeric OTP."""
    return f"{random.randint(0, 999999):06d}"


def get_verification_code_expiry() -> datetime:
    """Return the UTC expiry timestamp for a newly generated OTP."""
    return datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES)


def send_verification_email(first_name: str, to_email: str, verification_code: str) -> None:
    """Send the email verification OTP to the registered user."""
    smtp = _get_smtp_settings()
    smtp_user = str(smtp["user"])
    smtp_password = str(smtp["password"])

    if not smtp_user or not smtp_password:
        logger.error("SMTP credentials are not configured; verification email not sent.")
        return

    subject = "Verify Your Email Address"
    body = (
        f"Hello {first_name},\n\n"
        "Thank you for registering.\n\n"
        "Your verification code is:\n\n"
        f"{verification_code}\n\n"
        f"This code will expire in {OTP_EXPIRY_MINUTES} minutes.\n\n"
        "Regards,\n"
        "SaaS AI Custom Chatbot Team"
    )

    from_email = str(smtp["from_email"])

    message = MIMEMultipart()
    message["From"] = from_email
    message["To"] = to_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(str(smtp["host"]), int(smtp["port"]), timeout=30) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(from_email, to_email, message.as_string())
        logger.info("Verification email sent to %s", to_email)
    except smtplib.SMTPException:
        logger.exception("Failed to send verification email to %s", to_email)


def apply_verification_migrations(db_engine: Engine) -> None:
    """
    Add verification columns to an existing users table.

    create_all() only creates new tables; it does not alter existing ones.
    """
    inspector = inspect(db_engine)
    if "users" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("users")}
    statements: list[str] = []

    if "verification_code" not in existing_columns:
        statements.append(
            "ALTER TABLE users ADD COLUMN verification_code VARCHAR(6)"
        )
    if "verification_code_expires_at" not in existing_columns:
        statements.append(
            "ALTER TABLE users ADD COLUMN verification_code_expires_at "
            "TIMESTAMP WITH TIME ZONE"
        )

    # Allow the same mobile number across different accounts.
    unique_constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("users")
    }
    if "users_mobile_key" in unique_constraints:
        statements.append("ALTER TABLE users DROP CONSTRAINT users_mobile_key")

    if not statements:
        return

    with db_engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
