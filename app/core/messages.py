"""
Centralized API validation and response messages.

Keep user-facing strings here so routes and services stay free of hardcoded copy.
"""

# ---------------------------------------------------------------------------
# Signup — field validation
# ---------------------------------------------------------------------------

FIRST_NAME_REQUIRED = "First name is required."
FIRST_NAME_TOO_SHORT = "First name must be at least 2 characters long."
FIRST_NAME_TOO_LONG = "First name must not exceed 50 characters."
FIRST_NAME_INVALID = "First name must contain only alphabets."

LAST_NAME_REQUIRED = "Last name is required."
LAST_NAME_TOO_SHORT = "Last name must be at least 2 characters long."
LAST_NAME_TOO_LONG = "Last name must not exceed 50 characters."
LAST_NAME_INVALID = "Last name must contain only alphabets."

EMAIL_REQUIRED = "Email is required."
INVALID_EMAIL = "Please enter a valid email address."

MOBILE_REQUIRED = "Mobile number is required."
INVALID_MOBILE = "Mobile number must contain 8 to 15 digits only."

PASSWORD_REQUIRED = "Password is required."
PASSWORD_TOO_SHORT = "Password must be at least 8 characters long."
PASSWORD_TOO_LONG = "Password must not exceed 100 characters."
PASSWORD_POLICY_FAILED = (
    "Password must contain at least one uppercase letter, one lowercase letter, "
    "one number and one special character."
)

CONFIRM_PASSWORD_REQUIRED = "Confirm password is required."
PASSWORD_MISMATCH = "Password and confirm password do not match."

# ---------------------------------------------------------------------------
# Signup — database / business rules
# ---------------------------------------------------------------------------

EMAIL_ALREADY_EXISTS = "Email already registered."
MOBILE_ALREADY_EXISTS = "Mobile number already registered."

# ---------------------------------------------------------------------------
# Signup — success
# ---------------------------------------------------------------------------

USER_CREATED_SUCCESSFULLY = (
    "Registration completed successfully. Verification code sent to your email."
)

# ---------------------------------------------------------------------------
# Verification — field validation
# ---------------------------------------------------------------------------

VERIFICATION_CODE_REQUIRED = "Verification code is required."
VERIFICATION_CODE_INVALID_FORMAT = "Verification code must be exactly 6 digits."

# ---------------------------------------------------------------------------
# Verification — business rules
# ---------------------------------------------------------------------------

VERIFICATION_CODE_INVALID = "Invalid verification code."
VERIFICATION_CODE_NOT_FOUND = "Invalid verification code."
VERIFICATION_CODE_EXPIRED = "Verification code has expired."
USER_ALREADY_VERIFIED = "Account already verified."
USER_NOT_FOUND = "User not found."

# ---------------------------------------------------------------------------
# Verification — success / system
# ---------------------------------------------------------------------------

VERIFICATION_SUCCESS = "Account verified successfully."
VERIFICATION_CODE_RESENT = "Verification code has been sent successfully."
VERIFICATION_CODE_NOT_EXPIRED = (
    "Verification code is still active. Please use the existing code."
)
ACCOUNT_ALREADY_VERIFIED = "Account already verified."
INTERNAL_SERVER_ERROR = "An unexpected error occurred. Please try again later."

# ---------------------------------------------------------------------------
# Sign-in — field validation
# ---------------------------------------------------------------------------

# EMAIL_REQUIRED, INVALID_EMAIL, PASSWORD_REQUIRED reused from signup section.

# ---------------------------------------------------------------------------
# Sign-in — business rules
# ---------------------------------------------------------------------------

INVALID_CREDENTIALS = "Invalid email or password."
ACCOUNT_NOT_VERIFIED = "Please verify your account before signing in."
ACCOUNT_INACTIVE = "Your account is inactive. Please contact support."

# ---------------------------------------------------------------------------
# Sign-in — success
# ---------------------------------------------------------------------------

LOGIN_SUCCESS = "Login successful"

# ---------------------------------------------------------------------------
# Authentication — JWT / session
# ---------------------------------------------------------------------------

TOKEN_REQUIRED = "Authentication token is required."
INVALID_TOKEN = "Invalid authentication token."
TOKEN_EXPIRED = "Authentication token has expired."
TOKEN_BLACKLISTED = "Session has expired. Please sign in again."
SIGNOUT_SUCCESS = "Signed out successfully."
UNAUTHORIZED = "Unauthorized access."
