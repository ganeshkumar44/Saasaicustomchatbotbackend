"""Reusable HTML email templates for transactional messages."""

from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import datetime, timezone

COMPANY_NAME = "NexGenChat"
PRIMARY_COLOR = "#6C5CE7"
PRIMARY_DARK = "#5A4BD1"
TEXT_COLOR = "#374151"
MUTED_TEXT_COLOR = "#6B7280"
CARD_BACKGROUND = "#FFFFFF"
PAGE_BACKGROUND = "#F3F4F6"
OTP_BOX_BACKGROUND = "#F3F4F6"
FOOTER_BACKGROUND = "#F9FAFB"
BORDER_COLOR = "#E5E7EB"


@dataclass(frozen=True)
class OtpEmailContent:
    """Content fields for OTP-style transactional emails."""

    subject: str
    header_title: str
    greeting_name: str | None
    intro_text: str
    otp_code: str
    expiry_minutes: int
    security_note: str
    closing_text: str = "Thank you for using our service!"


def _greeting_line(greeting_name: str | None) -> str:
    if greeting_name and greeting_name.strip():
        return f"Hello {html.escape(greeting_name.strip())},"
    return "Hello,"


def _plain_otp_email(content: OtpEmailContent) -> str:
    greeting = (
        f"Hello {content.greeting_name.strip()},"
        if content.greeting_name and content.greeting_name.strip()
        else "Hello,"
    )
    return (
        f"{greeting}\n\n"
        f"{content.intro_text}\n\n"
        f"{content.otp_code}\n\n"
        f"This OTP is valid for {content.expiry_minutes} minutes. "
        f"Please do not share this code with anyone.\n\n"
        f"{content.security_note}\n\n"
        f"{content.closing_text}\n\n"
        f"Regards,\n"
        f"{COMPANY_NAME} Team"
    )


def _html_otp_email(content: OtpEmailContent) -> str:
    year = datetime.now(timezone.utc).year
    safe_otp = html.escape(content.otp_code.strip())
    expiry_label = "minute" if content.expiry_minutes == 1 else "minutes"

    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{html.escape(content.subject)}</title>
  </head>
  <body style="margin:0;padding:0;background-color:{PAGE_BACKGROUND};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:{TEXT_COLOR};">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:{PAGE_BACKGROUND};padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;background-color:{CARD_BACKGROUND};border-radius:12px;overflow:hidden;box-shadow:0 8px 24px rgba(17,24,39,0.08);">
            <tr>
              <td style="background-color:{PRIMARY_COLOR};padding:28px 24px;text-align:center;">
                <h1 style="margin:0;font-size:28px;line-height:1.2;font-weight:700;color:#FFFFFF;">
                  {html.escape(content.header_title)}
                </h1>
              </td>
            </tr>
            <tr>
              <td style="padding:32px 28px 24px;">
                <p style="margin:0 0 16px;font-size:16px;line-height:1.6;color:{TEXT_COLOR};">
                  {_greeting_line(content.greeting_name)}
                </p>
                <p style="margin:0 0 24px;font-size:16px;line-height:1.6;color:{TEXT_COLOR};">
                  {html.escape(content.intro_text)}
                </p>
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin:0 0 24px;">
                  <tr>
                    <td align="center" style="background-color:{OTP_BOX_BACKGROUND};border-radius:10px;padding:24px 16px;">
                      <span style="display:inline-block;font-size:36px;line-height:1.1;font-weight:700;letter-spacing:6px;color:{PRIMARY_COLOR};">
                        {safe_otp}
                      </span>
                    </td>
                  </tr>
                </table>
                <p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:{TEXT_COLOR};">
                  This OTP is valid for
                  <strong>{content.expiry_minutes} {expiry_label}</strong>.
                  Please do not share this code with anyone.
                </p>
                <p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:{MUTED_TEXT_COLOR};">
                  {html.escape(content.security_note)}
                </p>
                <p style="margin:0;font-size:15px;line-height:1.6;color:{TEXT_COLOR};">
                  {html.escape(content.closing_text)}
                </p>
              </td>
            </tr>
            <tr>
              <td style="background-color:{FOOTER_BACKGROUND};border-top:1px solid {BORDER_COLOR};padding:18px 24px;text-align:center;">
                <p style="margin:0;font-size:13px;line-height:1.5;color:{MUTED_TEXT_COLOR};">
                  &copy; {year} {html.escape(COMPANY_NAME)}. All rights reserved.
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def build_otp_email_bodies(content: OtpEmailContent) -> tuple[str, str]:
    """Return plain-text and HTML bodies for an OTP email."""
    return _plain_otp_email(content), _html_otp_email(content)


def build_signup_verification_email(
    first_name: str,
    verification_code: str,
    expiry_minutes: int,
) -> tuple[str, str, str]:
    """Build subject, plain body, and HTML body for signup verification."""
    content = OtpEmailContent(
        subject="Verify Your Email Address",
        header_title="Your OTP Code",
        greeting_name=first_name,
        intro_text="Your One-Time Password (OTP) for account verification is:",
        otp_code=verification_code,
        expiry_minutes=expiry_minutes,
        security_note="If you didn't request this code, please ignore this email.",
    )
    plain_body, html_body = build_otp_email_bodies(content)
    return content.subject, plain_body, html_body


@dataclass(frozen=True)
class NotificationEmailContent:
    """Content fields for informational notification emails."""

    subject: str
    header_title: str
    greeting_name: str | None
    intro_text: str
    highlight_text: str | None = None
    detail_lines: tuple[str, ...] = ()
    security_note: str | None = None
    closing_text: str = "Thank you for using our service!"


def _plain_notification_email(content: NotificationEmailContent) -> str:
    greeting = (
        f"Hello {content.greeting_name.strip()},"
        if content.greeting_name and content.greeting_name.strip()
        else "Hello,"
    )
    lines = [greeting, "", content.intro_text, ""]
    if content.highlight_text:
        lines.append(content.highlight_text)
        lines.append("")
    lines.extend(content.detail_lines)
    if content.detail_lines:
        lines.append("")
    if content.security_note:
        lines.append(content.security_note)
        lines.append("")
    lines.extend([content.closing_text, "", f"Regards,\n{COMPANY_NAME} Team"])
    return "\n".join(lines)


def _html_notification_email(content: NotificationEmailContent) -> str:
    year = datetime.now(timezone.utc).year
    detail_html = "".join(
        f'<p style="margin:0 0 12px;font-size:15px;line-height:1.6;color:{MUTED_TEXT_COLOR};">'
        f"{html.escape(line)}</p>"
        for line in content.detail_lines
    )
    highlight_html = ""
    if content.highlight_text:
        highlight_html = f"""
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin:0 0 24px;">
                  <tr>
                    <td align="center" style="background-color:{OTP_BOX_BACKGROUND};border-radius:10px;padding:24px 16px;">
                      <span style="display:inline-block;font-size:24px;line-height:1.3;font-weight:700;color:{PRIMARY_COLOR};">
                        {html.escape(content.highlight_text)}
                      </span>
                    </td>
                  </tr>
                </table>"""
    security_html = ""
    if content.security_note:
        security_html = f"""
                <p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:{MUTED_TEXT_COLOR};">
                  {html.escape(content.security_note)}
                </p>"""

    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{html.escape(content.subject)}</title>
  </head>
  <body style="margin:0;padding:0;background-color:{PAGE_BACKGROUND};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:{TEXT_COLOR};">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:{PAGE_BACKGROUND};padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;background-color:{CARD_BACKGROUND};border-radius:12px;overflow:hidden;box-shadow:0 8px 24px rgba(17,24,39,0.08);">
            <tr>
              <td style="background-color:{PRIMARY_COLOR};padding:28px 24px;text-align:center;">
                <h1 style="margin:0;font-size:28px;line-height:1.2;font-weight:700;color:#FFFFFF;">
                  {html.escape(content.header_title)}
                </h1>
              </td>
            </tr>
            <tr>
              <td style="padding:32px 28px 24px;">
                <p style="margin:0 0 16px;font-size:16px;line-height:1.6;color:{TEXT_COLOR};">
                  {_greeting_line(content.greeting_name)}
                </p>
                <p style="margin:0 0 24px;font-size:16px;line-height:1.6;color:{TEXT_COLOR};">
                  {html.escape(content.intro_text)}
                </p>
                {highlight_html}
                {detail_html}
                {security_html}
                <p style="margin:0;font-size:15px;line-height:1.6;color:{TEXT_COLOR};">
                  {html.escape(content.closing_text)}
                </p>
              </td>
            </tr>
            <tr>
              <td style="background-color:{FOOTER_BACKGROUND};border-top:1px solid {BORDER_COLOR};padding:18px 24px;text-align:center;">
                <p style="margin:0;font-size:13px;line-height:1.5;color:{MUTED_TEXT_COLOR};">
                  &copy; {year} {html.escape(COMPANY_NAME)}. All rights reserved.
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def build_notification_email_bodies(
    content: NotificationEmailContent,
) -> tuple[str, str]:
    """Return plain-text and HTML bodies for a notification email."""
    return _plain_notification_email(content), _html_notification_email(content)


def build_new_chatbot_created_email(
    *,
    first_name: str | None,
    chatbot_name: str,
) -> tuple[str, str, str]:
    """Build subject, plain body, and HTML body for new chatbot notifications."""
    from app.core import messages

    content = NotificationEmailContent(
        subject=messages.NOTIFICATION_NEW_CHATBOT_EMAIL_SUBJECT,
        header_title=messages.NOTIFICATION_NEW_CHATBOT_EMAIL_HEADER,
        greeting_name=first_name,
        intro_text=messages.NOTIFICATION_NEW_CHATBOT_EMAIL_INTRO,
        highlight_text=chatbot_name,
        detail_lines=(messages.NOTIFICATION_NEW_CHATBOT_EMAIL_DETAIL,),
        security_note=messages.NOTIFICATION_NEW_CHATBOT_EMAIL_SECURITY_NOTE,
    )
    plain_body, html_body = build_notification_email_bodies(content)
    return content.subject, plain_body, html_body


def build_chatbot_updated_email(
    *,
    first_name: str | None,
    chatbot_name: str,
    updated_by_label: str,
) -> tuple[str, str, str]:
    """Build subject, plain body, and HTML body for chatbot update notifications."""
    from app.core import messages

    content = NotificationEmailContent(
        subject=messages.NOTIFICATION_CHATBOT_UPDATED_EMAIL_SUBJECT,
        header_title=messages.NOTIFICATION_CHATBOT_UPDATED_EMAIL_HEADER,
        greeting_name=first_name,
        intro_text=messages.NOTIFICATION_CHATBOT_UPDATED_EMAIL_INTRO,
        highlight_text=chatbot_name,
        detail_lines=(f"Updated by: {updated_by_label}",),
        security_note=messages.NOTIFICATION_CHATBOT_UPDATED_EMAIL_SECURITY_NOTE,
    )
    plain_body, html_body = build_notification_email_bodies(content)
    return content.subject, plain_body, html_body


def build_forgot_password_email(
    verification_code: str,
    expiry_minutes: int,
) -> tuple[str, str, str]:
    """Build subject, plain body, and HTML body for forgot-password OTP."""
    content = OtpEmailContent(
        subject="Forgot Password Verification Code",
        header_title="Your OTP Code",
        greeting_name=None,
        intro_text="Your One-Time Password (OTP) for password reset is:",
        otp_code=verification_code,
        expiry_minutes=expiry_minutes,
        security_note=(
            "If you did not request a password reset, please ignore this email."
        ),
    )
    plain_body, html_body = build_otp_email_bodies(content)
    return content.subject, plain_body, html_body


@dataclass(frozen=True)
class NotificationEmailContent:
    """Content fields for informational notification emails."""

    subject: str
    header_title: str
    greeting_name: str | None
    intro_text: str
    highlight_text: str | None = None
    detail_lines: tuple[str, ...] = ()
    security_note: str | None = None
    closing_text: str = "Thank you for using our service!"


def _plain_notification_email(content: NotificationEmailContent) -> str:
    greeting = (
        f"Hello {content.greeting_name.strip()},"
        if content.greeting_name and content.greeting_name.strip()
        else "Hello,"
    )
    lines = [greeting, "", content.intro_text, ""]
    if content.highlight_text:
        lines.append(content.highlight_text)
        lines.append("")
    lines.extend(content.detail_lines)
    if content.detail_lines:
        lines.append("")
    if content.security_note:
        lines.append(content.security_note)
        lines.append("")
    lines.extend([content.closing_text, "", f"Regards,\n{COMPANY_NAME} Team"])
    return "\n".join(lines)


def _html_notification_email(content: NotificationEmailContent) -> str:
    year = datetime.now(timezone.utc).year
    detail_html = "".join(
        f'<p style="margin:0 0 12px;font-size:15px;line-height:1.6;color:{MUTED_TEXT_COLOR};">'
        f"{html.escape(line)}</p>"
        for line in content.detail_lines
    )
    highlight_html = ""
    if content.highlight_text:
        highlight_html = f"""
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin:0 0 24px;">
                  <tr>
                    <td align="center" style="background-color:{OTP_BOX_BACKGROUND};border-radius:10px;padding:24px 16px;">
                      <span style="display:inline-block;font-size:24px;line-height:1.3;font-weight:700;color:{PRIMARY_COLOR};">
                        {html.escape(content.highlight_text)}
                      </span>
                    </td>
                  </tr>
                </table>"""
    security_html = ""
    if content.security_note:
        security_html = f"""
                <p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:{MUTED_TEXT_COLOR};">
                  {html.escape(content.security_note)}
                </p>"""

    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{html.escape(content.subject)}</title>
  </head>
  <body style="margin:0;padding:0;background-color:{PAGE_BACKGROUND};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:{TEXT_COLOR};">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:{PAGE_BACKGROUND};padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;background-color:{CARD_BACKGROUND};border-radius:12px;overflow:hidden;box-shadow:0 8px 24px rgba(17,24,39,0.08);">
            <tr>
              <td style="background-color:{PRIMARY_COLOR};padding:28px 24px;text-align:center;">
                <h1 style="margin:0;font-size:28px;line-height:1.2;font-weight:700;color:#FFFFFF;">
                  {html.escape(content.header_title)}
                </h1>
              </td>
            </tr>
            <tr>
              <td style="padding:32px 28px 24px;">
                <p style="margin:0 0 16px;font-size:16px;line-height:1.6;color:{TEXT_COLOR};">
                  {_greeting_line(content.greeting_name)}
                </p>
                <p style="margin:0 0 24px;font-size:16px;line-height:1.6;color:{TEXT_COLOR};">
                  {html.escape(content.intro_text)}
                </p>
                {highlight_html}
                {detail_html}
                {security_html}
                <p style="margin:0;font-size:15px;line-height:1.6;color:{TEXT_COLOR};">
                  {html.escape(content.closing_text)}
                </p>
              </td>
            </tr>
            <tr>
              <td style="background-color:{FOOTER_BACKGROUND};border-top:1px solid {BORDER_COLOR};padding:18px 24px;text-align:center;">
                <p style="margin:0;font-size:13px;line-height:1.5;color:{MUTED_TEXT_COLOR};">
                  &copy; {year} {html.escape(COMPANY_NAME)}. All rights reserved.
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def build_notification_email_bodies(
    content: NotificationEmailContent,
) -> tuple[str, str]:
    """Return plain-text and HTML bodies for a notification email."""
    return _plain_notification_email(content), _html_notification_email(content)


def build_new_chatbot_created_email(
    *,
    first_name: str | None,
    chatbot_name: str,
) -> tuple[str, str, str]:
    """Build subject, plain body, and HTML body for new chatbot notifications."""
    from app.core import messages

    content = NotificationEmailContent(
        subject=messages.NOTIFICATION_NEW_CHATBOT_EMAIL_SUBJECT,
        header_title=messages.NOTIFICATION_NEW_CHATBOT_EMAIL_HEADER,
        greeting_name=first_name,
        intro_text=messages.NOTIFICATION_NEW_CHATBOT_EMAIL_INTRO,
        highlight_text=chatbot_name,
        detail_lines=(messages.NOTIFICATION_NEW_CHATBOT_EMAIL_DETAIL,),
        security_note=messages.NOTIFICATION_NEW_CHATBOT_EMAIL_SECURITY_NOTE,
    )
    plain_body, html_body = build_notification_email_bodies(content)
    return content.subject, plain_body, html_body


def build_chatbot_updated_email(
    *,
    first_name: str | None,
    chatbot_name: str,
    updated_by_label: str,
) -> tuple[str, str, str]:
    """Build subject, plain body, and HTML body for chatbot update notifications."""
    from app.core import messages

    content = NotificationEmailContent(
        subject=messages.NOTIFICATION_CHATBOT_UPDATED_EMAIL_SUBJECT,
        header_title=messages.NOTIFICATION_CHATBOT_UPDATED_EMAIL_HEADER,
        greeting_name=first_name,
        intro_text=messages.NOTIFICATION_CHATBOT_UPDATED_EMAIL_INTRO,
        highlight_text=chatbot_name,
        detail_lines=(f"Updated by: {updated_by_label}",),
        security_note=messages.NOTIFICATION_CHATBOT_UPDATED_EMAIL_SECURITY_NOTE,
    )
    plain_body, html_body = build_notification_email_bodies(content)
    return content.subject, plain_body, html_body
