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
KNOWLEDGE_BASE_UPLOAD_STARTED = "Knowledge base upload started."
KNOWLEDGE_BASE_UPDATE_STARTED = "Knowledge base update started."
KNOWLEDGE_BASE_UPDATED = "Knowledge base updated successfully."
SECURITY_SETTINGS_UPDATED = "Security settings updated successfully."
KNOWLEDGE_BASE_REQUIRED = "Please upload at least one knowledge base file or URL."
KNOWLEDGE_BASE_FILE_SIZE_EXCEEDED = (
    "Each knowledge base file must not exceed 2 MB."
)
KNOWLEDGE_BASE_UPLOAD_FAILED = (
    "Failed to upload knowledge base file. Please try again."
)
KNOWLEDGE_BASE_DELETE_FAILED = (
    "Failed to delete knowledge base file. Please try again."
)
KNOWLEDGE_BASE_DOWNLOAD_FAILED = (
    "Failed to process knowledge base file from storage. Please try again."
)
KNOWLEDGE_DOCUMENT_NOT_FOUND = "One or more knowledge base documents were not found."

INVALID_WIDGET_POSITION = "Invalid widget position. Allowed values are bottom-right and bottom-left."
INVALID_COLOR = "Invalid color. Please provide a valid HEX color code."
INVALID_DOMAIN = "Invalid domain URL provided."
INVALID_AI_MODEL = "Unsupported AI model selected."
AI_QUOTA_EXCEEDED = (
    "The AI service has reached its request limit. Please try again later."
)

# ---------------------------------------------------------------------------
# Playground
# ---------------------------------------------------------------------------

PLAYGROUND_SESSION_CREATED_SUCCESS = "Playground session created successfully."
PLAYGROUND_SESSION_DELETED_SUCCESS = "Playground session deleted successfully."
PLAYGROUND_SESSION_NOT_FOUND = "Playground session not found."
PLAYGROUND_SESSION_CHATBOT_MISMATCH = (
    "Playground session does not belong to the specified chatbot."
)

OPENAI_AUTHENTICATION_FAILED = "OpenAI API key is invalid or unauthorized."
OPENAI_RATE_LIMIT_EXCEEDED = (
    "The OpenAI service has reached its request limit. Please try again later."
)
OPENAI_REQUEST_TIMEOUT = "OpenAI request timed out. Please try again."
OPENAI_NETWORK_ERROR = "Unable to reach the OpenAI service. Please try again."
OPENAI_SERVICE_UNAVAILABLE = "The OpenAI service is temporarily unavailable."
OPENAI_REQUEST_FAILED = "Failed to generate an answer using OpenAI."
OPENAI_EMPTY_RESPONSE = "OpenAI returned an empty response."

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
ALLOWED_DOMAINS_ALREADY_ASSIGNED = (
    "One or more allowed domains are already assigned to another chatbot."
)
ALLOWED_DOMAINS_CONFLICT_DETAIL = (
    "The following domains are already assigned to another chatbot."
)

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
CHATBOT_DELETED_SUCCESS = "Chatbot deleted successfully."
CHATBOT_HARD_DELETED_SUCCESS = "Draft chatbot permanently deleted successfully."
CHATBOT_ALREADY_DELETED = "Chatbot has already been deleted."
CHATBOT_ACTIVATED_SUCCESS = "Chatbot activated successfully."
CHATBOT_ALREADY_ACTIVE = "Chatbot is already active."
SUPERADMIN_CHATBOT_PROTECTED = (
    "You are not authorized to modify SuperAdmin chatbots."
)
ONLY_DRAFT_CAN_BE_HARD_DELETED = (
    "Only draft chatbots can be permanently deleted."
)
CHATBOT_UNAVAILABLE = (
    "This chatbot is currently unavailable. It may have been deleted or there may be "
    "a temporary server issue. Please contact the website administrator."
)
CHATBOT_UNAVAILABLE_PUBLIC = (
    "This chatbot is currently unavailable. Please contact the website administrator."
)
RECENT_CONVERSATIONS_SUCCESS = "Recent conversations retrieved successfully."
NO_RECENT_CONVERSATIONS = "No recent conversations found."
CHATBOT_ANALYTICS_SUCCESS = "Chatbot analytics retrieved successfully."
NO_CHATBOT_ANALYTICS = "No chatbot analytics found."
MERGED_CHATBOT_ANALYTICS_SUCCESS = "Merged chatbot analytics retrieved successfully."

# ---------------------------------------------------------------------------
# Chat History
# ---------------------------------------------------------------------------

CHAT_SESSION_LIST_SUCCESS = "Chat sessions retrieved successfully."
CHAT_HISTORY_SUCCESS = "Chat history retrieved successfully."
NO_CHAT_HISTORY = "No chat history found."

# ---------------------------------------------------------------------------
# Graphs
# ---------------------------------------------------------------------------

INVALID_DATE_RANGE = (
    "Invalid date range. Allowed values are 7d, 30d, 3m, 6m, and 1y."
)

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------

THEME_UPDATED_SUCCESS = "Theme updated successfully."
INVALID_THEME = "Invalid theme. Allowed values are dark and light."
THEME_NOT_FOUND = "Theme preference not found."

# ---------------------------------------------------------------------------
# Notification Settings
# ---------------------------------------------------------------------------

NOTIFICATION_SETTINGS_RETRIEVED_SUCCESS = (
    "Notification settings retrieved successfully."
)
NOTIFICATION_SETTINGS_UPDATED_SUCCESS = (
    "Notification settings updated successfully."
)

NOTIFICATION_NEW_CHATBOT_EMAIL_SUBJECT = "New Chatbot Created"
NOTIFICATION_NEW_CHATBOT_EMAIL_HEADER = "New Chatbot Created"
NOTIFICATION_NEW_CHATBOT_EMAIL_INTRO = (
    "A new chatbot has been created on your account:"
)
NOTIFICATION_NEW_CHATBOT_EMAIL_DETAIL = (
    "You can review and manage your chatbot from your dashboard."
)
NOTIFICATION_NEW_CHATBOT_EMAIL_SECURITY_NOTE = (
    "If you did not create this chatbot, please review your account security."
)

NOTIFICATION_CHATBOT_UPDATED_EMAIL_SUBJECT = "Chatbot Updated - Review Changes"
NOTIFICATION_CHATBOT_UPDATED_EMAIL_HEADER = "Chatbot Updated"
NOTIFICATION_CHATBOT_UPDATED_EMAIL_INTRO = (
    "Your chatbot was recently updated. Please review the changes:"
)
NOTIFICATION_CHATBOT_UPDATED_EMAIL_SECURITY_NOTE = (
    "If you did not authorize these changes, please review your account security."
)

# ---------------------------------------------------------------------------
# Welcome email (post-verification)
# ---------------------------------------------------------------------------

WELCOME_EMAIL_SUBJECT = "Welcome to NexGenChat – Your Account is Ready!"
WELCOME_EMAIL_HEADER = "Welcome to NexGenChat"
WELCOME_EMAIL_CONGRATULATIONS = "Congratulations! 🎉"
WELCOME_EMAIL_INTRO = (
    "Your NexGenChat account has been successfully created and verified."
)
WELCOME_EMAIL_BODY = (
    "You can now log in and start creating AI-powered chatbots for your website."
)
WELCOME_EMAIL_LOGIN_LABEL = "Login URL:"
WELCOME_EMAIL_SECURITY_NOTE = (
    "If you did not create this account, please contact our support team immediately."
)
WELCOME_EMAIL_CLOSING = "Thank you for choosing NexGenChat."
WELCOME_EMAIL_SIGN_OFF = "Best Regards,\nNexGenChat Team"

# ---------------------------------------------------------------------------
# Password reset confirmation email
# ---------------------------------------------------------------------------

PASSWORD_RESET_SUCCESS_EMAIL_SUBJECT = "Your NexGenChat Password Has Been Changed"
PASSWORD_RESET_SUCCESS_EMAIL_HEADER = "Password Changed"
PASSWORD_RESET_SUCCESS_EMAIL_INTRO = (
    "Your NexGenChat account password has been changed successfully."
)
PASSWORD_RESET_SUCCESS_EMAIL_BODY = "You can now log in using your new password."
PASSWORD_RESET_SUCCESS_EMAIL_LOGIN_LABEL = "Login URL:"
PASSWORD_RESET_SUCCESS_EMAIL_SECURITY_NOTE = (
    "If you did NOT perform this action, please reset your password immediately "
    "or contact support."
)
PASSWORD_RESET_SUCCESS_EMAIL_SIGN_OFF = "Best Regards,\nNexGenChat Team"

# ---------------------------------------------------------------------------
# User Details
# ---------------------------------------------------------------------------

USER_DETAILS_FETCH_SUCCESS = "User details retrieved successfully."
USER_DETAILS_CREATED = "User details created successfully."
USER_DETAILS_UPDATED = "User details updated successfully."
USER_SUBSCRIPTION_DETAILS_RETRIEVED_SUCCESS = (
    "User subscription details retrieved successfully."
)
USER_SUBSCRIPTION_DETAILS_NOT_FOUND = "User subscription details not found."
INVALID_IMAGE_TYPE = "Invalid image type. Allowed formats are JPG, JPEG, PNG, and WEBP."
IMAGE_SIZE_EXCEEDED = "Profile image size must not exceed 500 KB."
PROFILE_IMAGE_UPLOAD_FAILED = "Failed to upload profile image. Please try again."
PROFILE_IMAGE_UPDATED = "Profile image updated successfully."
PROFILE_PICTURE_REMOVED_SUCCESS = "Profile picture removed successfully."
PROFILE_PICTURE_NOT_FOUND = "Profile picture does not exist."
USER_PROFILE_NOT_FOUND = "User profile not found."
PROFILE_IMAGE_DELETE_FAILED = "Failed to remove profile picture. Please try again."

LOGIN_HISTORY_RETRIEVED_SUCCESS = "Login history retrieved successfully."
LOGIN_HISTORY_NOT_FOUND = "No login history found."

CURRENT_PASSWORD_REQUIRED = "Current password is required."
CURRENT_PASSWORD_INVALID = "Current password is incorrect."
NEW_PASSWORD_REQUIRED = "New password is required."
NEW_PASSWORD_SAME_AS_CURRENT = (
    "New password must be different from your current password."
)
NEW_PASSWORD_TOO_SIMILAR = (
    "New password is too similar to your current password. "
    "Please choose a more secure password."
)
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

# ---------------------------------------------------------------------------
# Manage Users
# ---------------------------------------------------------------------------

USERS_RETRIEVED_SUCCESS = "Users retrieved successfully."
USER_DETAILS_RETRIEVED_SUCCESS = "User details retrieved successfully."
USER_UPDATED_SUCCESS = "User updated successfully."
USER_ACTIVATED_SUCCESS = "User activated successfully."
USER_DEACTIVATED_SUCCESS = "User deactivated successfully."
USER_DELETED_SUCCESS = "User deleted successfully."
SELF_ACTION_NOT_ALLOWED = (
    "You cannot deactivate or delete your own administrator or SuperAdmin account."
)
INVALID_USER_STATUS_ACTION = "Invalid account action. Allowed values are activate, deactivate, and delete."
INVALID_USER_ROLE = "Invalid role. Allowed values are superadmin, admin, and user."
INVALID_ASSIGNABLE_ROLE = "Invalid role. Allowed values are user and admin."
SUPERADMIN_REQUIRED = "SuperAdmin access is required to perform this action."
ROLE_UPDATED_SUCCESS = "User role updated successfully."
CANNOT_MODIFY_SUPERADMIN = "The SuperAdmin role cannot be modified."
SUPERADMIN_ROLE_PROTECTED = CANNOT_MODIFY_SUPERADMIN
ONLY_SUPERADMIN_CAN_ASSIGN_ADMIN = (
    "Only SuperAdmin can assign or remove Admin privileges."
)
CANNOT_MANAGE_SUPERADMIN = "You cannot manage SuperAdmin accounts."

# ---------------------------------------------------------------------------
# Manage Chatbot
# ---------------------------------------------------------------------------

MANAGE_CHATBOT_PERMANENTLY_DELETED_SUCCESS = (
    "Chatbot permanently deleted successfully."
)
MANAGE_CHATBOT_PERMANENT_DELETE_FORBIDDEN = (
    "You do not have permission to permanently delete this chatbot."
)

COMPANY_TOO_LONG = "Company name must not exceed 150 characters."
BIO_TOO_LONG = "Bio must not exceed 1000 characters."

# ---------------------------------------------------------------------------
# Chat session lifecycle
# ---------------------------------------------------------------------------

CHAT_SESSION_CLOSED = "Chat session closed successfully."
CHAT_SESSION_UPDATED = "Chat session updated successfully."
CHAT_ALREADY_CLOSED = "Chat session is already closed."
CHAT_MARKED_RESOLVED = "Chat session marked as resolved."
CHAT_MARKED_UNRESOLVED = "Chat session marked as unresolved."
INVALID_SESSION_STATUS = "Invalid session status. Allowed values are active and closed."
INVALID_RESOLUTION_STATUS = (
    "Invalid resolution status. Allowed values are pending, resolved, and unresolved."
)
SESSION_NOT_FOUND = "Chat session not found."
INVALID_SESSION = "Invalid session for this chatbot."
CHAT_SESSION_NOT_CLOSED = "Chat session must be closed before submitting feedback."
SESSION_STATUS_REQUIRED = "At least one status field is required."
SESSION_NOT_ACTIVE = "Chat session is not active."
CHAT_FEEDBACK_REQUIRED = "Please provide your feedback before closing the chat."
CHAT_END_CONFIRMATION = "Are you sure you want to end this chat?"
CHAT_END_CONFIRMATION_SUBTITLE = (
    "Your feedback will help us improve your chat experience."
)
CHAT_FEEDBACK_QUESTION = "Are you satisfied with our AI responses?"
THANK_YOU_FEEDBACK = "Your chat has ended. Thank you for your feedback."
START_NEW_CHAT = "Start New Chat"

CHATBOT_CREATION_LIMIT_REACHED = (
    "You have reached your chatbot creation limit for the {plan_name} plan. "
    "Please upgrade your subscription to create more chatbots."
)

WEBSITE_MESSAGE_LIMIT_REACHED = (
    "You have reached your chatbot message limit. Please upgrade your subscription."
)
PLAYGROUND_MESSAGE_LIMIT_REACHED = (
    "You have reached your Playground message limit for this chatbot."
)

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
VISITOR_EMAIL_REQUIRED = "Email address is required."
VISITOR_PHONE_REQUIRED = "Phone number is required."
VISITOR_SKIP_NOT_ALLOWED = "All visitor details are required to continue."
VISITOR_DETAILS_SAVED = "Visitor details saved successfully."
THANK_YOU_START_CHAT = "Thank you! You can now ask your question."
ONBOARDING_INCOMPLETE = "Please complete visitor details before chatting."
INVALID_VISITOR_STEP = "Invalid onboarding step."

# ---------------------------------------------------------------------------
# Website feedback
# ---------------------------------------------------------------------------

FEEDBACK_RATING_REQUIRED = "Rating is required."
FEEDBACK_RATING_INVALID = "Rating must be an integer between 1 and 5."
FEEDBACK_NAME_REQUIRED = "Name is required."
FEEDBACK_NAME_TOO_LONG = "Name must not exceed 100 characters."
FEEDBACK_EMAIL_REQUIRED = "Email is required."
FEEDBACK_EMAIL_INVALID = "Please enter a valid email address."
FEEDBACK_PHONE_TOO_LONG = "Phone number must not exceed 20 characters."
FEEDBACK_MESSAGE_TOO_LONG = "Feedback message must not exceed 2000 characters."
FEEDBACK_SUBMITTED_SUCCESS = "Thank you for your feedback."
FEEDBACK_OWNER_EMAIL_SUBJECT = "New Website Feedback Received - NexGenChat"
FEEDBACK_OWNER_EMAIL_HEADER = "New Website Feedback"
FEEDBACK_OWNER_EMAIL_INTRO = (
    "A user has submitted feedback about the NexGenChat platform."
)

# ---------------------------------------------------------------------------
# Billing foundation
# ---------------------------------------------------------------------------

BILLING_PLANS_RETRIEVED_SUCCESS = "Billing plans retrieved successfully."
BILLING_CURRENT_PLAN_RETRIEVED_SUCCESS = "Current billing plan retrieved successfully."
BILLING_PAYMENT_HISTORY_RETRIEVED_SUCCESS = (
    "Payment history retrieved successfully."
)
BILLING_SUBSCRIPTION_HISTORY_RETRIEVED_SUCCESS = (
    "Subscription history retrieved successfully."
)
BILLING_INVOICES_RETRIEVED_SUCCESS = "Invoices retrieved successfully."
BILLING_ACCESS_DENIED = "You are not authorized to view this billing information."
BILLING_USER_NOT_FOUND = "Billing user not found."
BILLING_PLAN_NOT_FOUND = "Subscription plan not found."
BILLING_PLAN_INACTIVE = "The selected plan is not available."
BILLING_CYCLE_INVALID = (
    "Invalid billing cycle. Allowed values are monthly, six_month, and yearly."
)
BILLING_ALREADY_ON_PLAN = "You are already subscribed to this plan."
BILLING_CHECKOUT_PREPARED_SUCCESS = "Checkout preview prepared successfully."
BILLING_PLAN_COMPARISON_RETRIEVED_SUCCESS = (
    "Plan comparison retrieved successfully."
)
BILLING_CHECKOUT_FREE_PLAN = (
    "Free plan does not require payment. Contact support to switch to Free."
)
BILLING_ORDER_CREATED_SUCCESS = "Payment order created successfully."
BILLING_ORDER_AMOUNT_INVALID = "Payable amount must be greater than zero."
BILLING_RAZORPAY_NOT_CONFIGURED = (
    "Payment gateway is not configured. Please contact support."
)
BILLING_RAZORPAY_ORDER_FAILED = (
    "Unable to create payment order. Please try again in a moment."
)
BILLING_RAZORPAY_NETWORK_ERROR = (
    "Payment gateway is temporarily unreachable. Please try again."
)
BILLING_PAYMENT_VERIFIED_SUCCESS = "Payment verified successfully."
BILLING_PAYMENT_VERIFICATION_FAILED = "Payment verification failed."
BILLING_PAYMENT_ALREADY_VERIFIED = "Payment already verified."
BILLING_PAYMENT_NOT_FOUND = "Payment transaction not found."
BILLING_PAYMENT_ORDER_INVALID = "Invalid or unknown payment order."
BILLING_PAYMENT_NOT_PENDING = "This payment cannot be verified in its current state."
BILLING_PAYMENT_DETAIL_RETRIEVED_SUCCESS = "Payment details retrieved successfully."
BILLING_SUBSCRIPTION_CREATED_SUCCESS = "Subscription created successfully."
BILLING_SUBSCRIPTION_REQUIRED = "A Razorpay subscription id is required."
BILLING_SUBSCRIPTION_NOT_FOUND = "Subscription not found."
BILLING_SUBSCRIPTION_INVALID = "Invalid or inactive subscription."
BILLING_SUBSCRIPTION_EXISTS = "An active auto-renew subscription already exists."
BILLING_SUBSCRIPTION_ALREADY_ACTIVE = "Auto renew is already enabled."
BILLING_SUBSCRIPTION_ALREADY_DISABLED = "Auto renew is already disabled."
BILLING_SUBSCRIPTION_CANCELLED = "This subscription has already been cancelled."
BILLING_AUTO_RENEW_DISABLED_SUCCESS = (
    "Auto renew disabled. Your plan stays active until the current billing period ends."
)
BILLING_AUTO_RENEW_ENABLED_SUCCESS = "Auto renew enabled successfully."
BILLING_AUTO_RENEW_REQUIRED = "Auto renew must be enabled to create a subscription."
BILLING_SUBSCRIPTION_CANCELLED_SUCCESS = (
    "Auto renewal has been disabled. Your current plan will remain active "
    "until the billing period ends."
)
BILLING_PAYMENT_RETRY_SUCCESS = "Retry payment order created successfully."
BILLING_PAYMENT_ALREADY_SUCCESSFUL = "This payment already succeeded and cannot be retried."
BILLING_PAYMENT_RETRY_PENDING = "This payment is still pending and cannot be retried."
BILLING_PAYMENT_RETRY_INVALID = (
    "Only failed payments can be retried."
)
BILLING_SUBSCRIPTION_STATUS_RETRIEVED_SUCCESS = (
    "Subscription status retrieved successfully."
)
BILLING_RAZORPAY_PLAN_FAILED = (
    "Unable to prepare the subscription plan. Please try again."
)
BILLING_RAZORPAY_SUBSCRIPTION_FAILED = (
    "Unable to create subscription. Please try again in a moment."
)
BILLING_RAZORPAY_CUSTOMER_FAILED = (
    "Unable to create payment customer. Please try again."
)
BILLING_INVOICE_NOT_FOUND = "Invoice not found."
BILLING_INVOICE_PDF_MISSING = "Invoice PDF is not available yet."
BILLING_INVOICE_DOWNLOAD_FAILED = "Unable to download the invoice PDF."
BILLING_INVOICE_EMAIL_FAILED = "Unable to send the invoice email. Please try again."
BILLING_INVOICE_RESENT_SUCCESS = "Invoice email sent successfully."
BILLING_INVOICE_DETAIL_RETRIEVED_SUCCESS = "Invoice details retrieved successfully."
BILLING_INVOICE_CREATED_SUCCESS = "Invoice generated successfully."

