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
ACCOUNT_DEACTIVATED = (
    "Your account has been deactivated. Please contact the administrator."
)

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

# ---------------------------------------------------------------------------
# Chatbot Settings
# ---------------------------------------------------------------------------

CHATBOT_ID_REQUIRED = "Chatbot ID is required."
CHATBOT_NOT_FOUND = "Chatbot not found."
CHATBOT_SETTINGS_NOT_FOUND = "Chatbot settings not found."
UNAUTHORIZED_CHATBOT_ACCESS = "You are not authorized to access this chatbot."
CHATBOT_DETAILS_FETCH_SUCCESS = "Chatbot details retrieved successfully."

GENERAL_SETTINGS_UPDATED = "General settings updated successfully."
APPEARANCE_UPDATED = "Appearance settings updated successfully."
MESSAGES_UPDATED = "Chat messages updated successfully."
KNOWLEDGE_BASE_UPDATED = "Knowledge base updated successfully."
SECURITY_SETTINGS_UPDATED = "Security settings updated successfully."
KNOWLEDGE_BASE_REQUIRED = "Please upload at least one knowledge base file or URL."
KNOWLEDGE_DOCUMENT_NOT_FOUND = "One or more knowledge base documents were not found."

INVALID_WIDGET_POSITION = "Invalid widget position. Allowed values are bottom-right and bottom-left."
INVALID_COLOR = "Invalid color. Please provide a valid HEX color code."
INVALID_DOMAIN = "Invalid domain URL provided."
INVALID_AI_MODEL = "Invalid AI model."

CHATBOT_NAME_REQUIRED = "Chatbot name is required."
CHATBOT_NAME_TOO_LONG = "Chatbot name must not exceed 100 characters."
DESCRIPTION_REQUIRED = "Description is required."
DESCRIPTION_TOO_LONG = "Description must not exceed 1000 characters."
CHAT_TITLE_REQUIRED = "Chat title is required."
CHAT_TITLE_TOO_LONG = "Chat title must not exceed 100 characters."
WELCOME_MESSAGE_REQUIRED = "Welcome message is required."
WELCOME_MESSAGE_TOO_LONG = "Welcome message must not exceed 1000 characters."
INPUT_PLACEHOLDER_REQUIRED = "Input placeholder is required."
INPUT_PLACEHOLDER_TOO_LONG = "Input placeholder must not exceed 150 characters."
ALLOWED_DOMAINS_REQUIRED = "At least one allowed domain is required."

# ---------------------------------------------------------------------------
# Chatbot Builder
# ---------------------------------------------------------------------------

DRAFT_CHATBOT_EXISTS = "Existing draft chatbot found."
DRAFT_CHATBOT_CREATED = "Draft chatbot created successfully."

# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

CHATBOT_LIST_SUCCESS = "Chatbot list retrieved successfully."
NO_CHATBOTS_FOUND = "No chatbots found."

# ---------------------------------------------------------------------------
# User Details
# ---------------------------------------------------------------------------

USER_DETAILS_FETCH_SUCCESS = "User details retrieved successfully."
USER_DETAILS_CREATED = "User details created successfully."
USER_DETAILS_UPDATED = "User details updated successfully."

CURRENT_PASSWORD_REQUIRED = "Current password is required."
CURRENT_PASSWORD_INVALID = "Current password is incorrect."
NEW_PASSWORD_REQUIRED = "New password is required."
NEW_PASSWORD_SAME_AS_CURRENT = "New password cannot be the same as the current password."
CONFIRM_NEW_PASSWORD_REQUIRED = "Confirm new password is required."
PASSWORD_UPDATED_SUCCESS = "Password updated successfully."

ACCOUNT_UPDATED_SUCCESS = "Account updated successfully."
ACCOUNT_ACTIVATED = "Account activated successfully."
ACCOUNT_ALREADY_ACTIVATED = "Account is already active."
ACCOUNT_ALREADY_DEACTIVATED = "Account is already deactivated."
ACCOUNT_DELETED = "Account deleted successfully."
ACCOUNT_ALREADY_DELETED = "Account has already been deleted."
DELETE_SUCCESS = "Account deleted successfully."
DEACTIVATE_SUCCESS = "Account deactivated successfully."
ACTIVATE_SUCCESS = "Account activated successfully."
ADMIN_ACCESS_REQUIRED = "Administrator access is required to perform this action."

INVALID_ACTION = "Invalid account action."
INVALID_WEBSITE = "Please enter a valid website URL."
INVALID_LANGUAGE = "Invalid language. Only English is supported at this time."
UNAUTHORIZED_ACTION = "You are not authorized to perform this action."

COMPANY_TOO_LONG = "Company name must not exceed 150 characters."
BIO_TOO_LONG = "Bio must not exceed 1000 characters."

# ---------------------------------------------------------------------------
# Widget visitor onboarding
# ---------------------------------------------------------------------------

VISITOR_NAME_QUESTION = "What's your good name?"
VISITOR_EMAIL_QUESTION = "What's your email address?"
VISITOR_PHONE_QUESTION = "What's your phone number?"
VISITOR_NAME_REQUIRED = "Please enter your name."
VISITOR_NAME_TOO_SHORT = "Name must be at least 2 characters long."
VISITOR_NAME_TOO_LONG = "Name must not exceed 100 characters."
INVALID_VISITOR_NAME = "Name must contain only alphabets and spaces."
PLEASE_ENTER_NAME = "Please enter your name."
PLEASE_ENTER_EMAIL = "Please enter your email address."
PLEASE_ENTER_PHONE = "Please enter your phone number."
VISITOR_DETAILS_SAVED = "Visitor details saved successfully."
THANK_YOU_START_CHAT = "Thank you! You can now ask your question."
ONBOARDING_INCOMPLETE = "Please complete visitor details before chatting."
INVALID_VISITOR_STEP = "Invalid onboarding step."
