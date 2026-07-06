console.log("Widget Loaded");

const API_BASE_URL = "__WIDGET_API_BASE_URL__";

const chatbotKey = document.currentScript.getAttribute("data-chatbot-key");

console.log(chatbotKey);

const SESSION_STORAGE_KEY = "chat_session_id";

function getVisitorStorageKey(publicKey) {
  return `chat_visitor_key_${publicKey}`;
}

function getStoredVisitorKey(publicKey) {
  return localStorage.getItem(getVisitorStorageKey(publicKey));
}

function storeVisitorKey(publicKey, visitorKey) {
  if (visitorKey) {
    localStorage.setItem(getVisitorStorageKey(publicKey), visitorKey);
  }
}

const CHAT_END_CONFIRMATION = "Are you sure you want to end this chat?";
const CHAT_END_CONFIRMATION_SUBTITLE =
  "Your feedback will help us improve your chat experience.";
const CHAT_FEEDBACK_QUESTION = "Are you satisfied with our AI responses?";
const THANK_YOU_FEEDBACK = "Your chat has ended. Thank you for your feedback.";
const START_NEW_CHAT_LABEL = "Start New Chat";
const CHATBOT_UNAVAILABLE_MESSAGE =
  "This chatbot is currently unavailable. It may have been deleted or there may be a temporary server issue. Please contact the website administrator.";

function getDefaultConfig() {
  return {
    chat_title: "Chat Assistant",
    welcome_message: "",
    primary_color: "#4F46E5",
    text_color: "#FFFFFF",
    show_avatar: true,
    typing_indicator: true,
    widget_position: "bottom-right",
    allowed_domains: "*",
    input_placeholder: "Type your message...",
  };
}

function getFeedbackPendingKey(sessionId) {
  return `chat_feedback_pending_${sessionId}`;
}

function setFeedbackPending(sessionId, pending) {
  if (pending) {
    localStorage.setItem(getFeedbackPendingKey(sessionId), "true");
  } else {
    localStorage.removeItem(getFeedbackPendingKey(sessionId));
  }
}

function isFeedbackPending(sessionId) {
  return localStorage.getItem(getFeedbackPendingKey(sessionId)) === "true";
}

async function startChatSession(publicKey, visitorKey = null) {
  const storedVisitorKey = visitorKey || getStoredVisitorKey(publicKey);
  const requestBody = {
    public_key: publicKey,
  };

  if (storedVisitorKey) {
    requestBody.visitor_key = storedVisitorKey;
  }

  const response = await fetch(`${API_BASE_URL}/v1/widget/session/start`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(requestBody),
  });

  const data = await response.json();

  if (data.chatbot_available === false) {
    const error = new Error("Chatbot unavailable");
    error.chatbotUnavailable = true;
    throw error;
  }

  if (!response.ok || !data.success || !data.session_id) {
    throw new Error("Failed to start chat session");
  }

  localStorage.setItem(SESSION_STORAGE_KEY, data.session_id);
  return data.session_id;
}

async function isSessionValid(sessionId) {
  const response = await fetch(
    `${API_BASE_URL}/v1/widget/chat-history/${sessionId}`
  );
  if (!response.ok) {
    return false;
  }

  const data = await response.json();
  if (data.chatbot_available === false) {
    return false;
  }

  return data.success !== false;
}

async function ensureChatSession(publicKey) {
  const existingSession = localStorage.getItem(SESSION_STORAGE_KEY);

  if (existingSession) {
    const valid = await isSessionValid(existingSession);
    if (valid) {
      return existingSession;
    }
    localStorage.removeItem(SESSION_STORAGE_KEY);
  }

  return startChatSession(publicKey, getStoredVisitorKey(publicKey));
}

async function fetchChatHistory(sessionId) {
  const response = await fetch(
    `${API_BASE_URL}/v1/widget/chat-history/${sessionId}`
  );

  if (!response.ok) {
    return {
      messages: [],
      visitor_step: "completed",
      question: null,
      can_skip: false,
      onboarding_complete: true,
      is_active: "active",
      is_resolved: "pending",
    };
  }

  const data = await response.json();

  if (data.chatbot_available === false) {
    return {
      chatbot_available: false,
      message: data.message || CHATBOT_UNAVAILABLE_MESSAGE,
      messages: [],
      visitor_step: "completed",
      question: null,
      can_skip: false,
      onboarding_complete: true,
      is_active: "active",
      is_resolved: "pending",
    };
  }

  if (!data.success) {
    return {
      messages: [],
      visitor_step: "completed",
      question: null,
      can_skip: false,
      onboarding_complete: true,
      is_active: "active",
      is_resolved: "pending",
    };
  }

  return {
    chatbot_available: true,
    messages: Array.isArray(data.messages) ? data.messages : [],
    visitor_step: data.visitor_step || "completed",
    question: data.question || null,
    can_skip: Boolean(data.can_skip),
    onboarding_complete: data.onboarding_complete !== false,
    is_active: data.is_active || "active",
    is_resolved: data.is_resolved || "pending",
  };
}

async function updateChatSessionStatus(publicKey, sessionId, isActive, isResolved) {
  const response = await fetch(`${API_BASE_URL}/v1/widget/chat-session/status`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      public_key: publicKey,
      session_id: sessionId,
      is_active: isActive,
      is_resolved: isResolved,
    }),
  });

  const data = await response.json();
  return { response, data };
}

async function loadWidget(publicKey) {
  let configResponse;

  try {
    const response = await fetch(`${API_BASE_URL}/v1/widget/config/${publicKey}`);
    configResponse = await response.json();
  } catch (error) {
    initWidget(getDefaultConfig(), publicKey, null, {}, {
      chatbotUnavailable: true,
    });
    return;
  }

  const configData = configResponse.data || getDefaultConfig();
  const unavailableMessage =
    configResponse.message || CHATBOT_UNAVAILABLE_MESSAGE;

  if (configResponse.chatbot_available === false) {
    initWidget(configData, publicKey, null, {}, {
      chatbotUnavailable: true,
      unavailableMessage,
    });
    return;
  }

  if (!configResponse.success || !configResponse.data) {
    initWidget(getDefaultConfig(), publicKey, null, {}, {
      chatbotUnavailable: true,
      unavailableMessage,
    });
    return;
  }

  try {
    const sessionId = await ensureChatSession(publicKey);
    const historyData = await fetchChatHistory(sessionId);

    if (historyData.chatbot_available === false) {
      initWidget(configData, publicKey, null, {}, {
        chatbotUnavailable: true,
        unavailableMessage: historyData.message || unavailableMessage,
      });
      return;
    }

    console.log("Chat session:", sessionId);
    console.log(configResponse);
    console.log("Chat history:", historyData);

    initWidget(configData, publicKey, sessionId, historyData);
  } catch (error) {
    initWidget(configData, publicKey, null, {}, {
      chatbotUnavailable: true,
      unavailableMessage,
    });
  }
}

if (!chatbotKey) {
  console.error("Widget: missing data-chatbot-key");
} else {
  loadWidget(chatbotKey).catch((error) => {
    console.error("Widget:", error);
  });
}

const CHATBOT_ICON_SVG = `<svg fill="#ffffff" width="800px" height="800px" viewBox="0 0 256 256" id="Flat" xmlns="http://www.w3.org/2000/svg">
  <path d="M207.05811,88.666q-1.10724-1.103-2.24146-2.16895l24.84009-24.84033a7.99984,7.99984,0,0,0-11.31348-11.31348L192.3728,76.3135a111.42105,111.42105,0,0,0-128.55444.19092L37.65674,50.34328A7.99984,7.99984,0,0,0,26.34326,61.65676L51.40283,86.71633A113.38256,113.38256,0,0,0,16,169.12893V192a16.01833,16.01833,0,0,0,16,16H224a16.01833,16.01833,0,0,0,16-16V168A111.25215,111.25215,0,0,0,207.05811,88.666ZM92,168a12,12,0,1,1,12-12A12,12,0,0,1,92,168Zm72,0a12,12,0,1,1,12-12A12,12,0,0,1,164,168Z"/>
</svg>`;

const SEND_ICON_SVG = `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M12 19V5M6 11l6-6 6 6" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

const OPEN_CHAT_ICON_SVG = `<svg fill="#ffffff" width="800px" height="800px" viewBox="0 0 256.00098 256.00098" id="Flat" xmlns="http://www.w3.org/2000/svg">
  <path d="M232.002,64.00293v128a16.02084,16.02084,0,0,1-16,16l-133.95312.375-31.75,26.69531a15.86968,15.86968,0,0,1-10.25,3.77344,16.11258,16.11258,0,0,1-6.79688-1.51563,15.8614,15.8614,0,0,1-9.25-14.50781V64.00293a16.02085,16.02085,0,0,1,16-16h176A16.02084,16.02084,0,0,1,232.002,64.00293Z"/>
</svg>`;

const MINIMIZE_ICON_SVG = `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M6 12h12" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>`;

const MAXIMIZE_ICON_SVG = `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

const RESTORE_ICON_SVG = `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M4 14h6v6M20 10h-6V4M14 10l7-7M3 21l7-7" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

function hexToRgba(hex, alpha) {
  const normalized = hex.replace("#", "");
  const full =
    normalized.length === 3
      ? normalized
          .split("")
          .map((c) => c + c)
          .join("")
      : normalized;
  const int = parseInt(full, 16);
  const r = (int >> 16) & 255;
  const g = (int >> 8) & 255;
  const b = int & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function initWidget(config, publicKey, sessionId, historyData = {}, options = {}) {
  const chatbotUnavailable = Boolean(options.chatbotUnavailable);
  const unavailableMessage =
    options.unavailableMessage || CHATBOT_UNAVAILABLE_MESSAGE;
  let currentSessionId = sessionId;
  const historyMessages = historyData.messages || [];
  let visitorStep = historyData.visitor_step || "completed";
  let onboardingComplete = historyData.onboarding_complete !== false;
  let canSkip = Boolean(historyData.can_skip);
  let chatClosed = historyData.is_active === "closed";
  let hasAiResponse =
    onboardingComplete && Array.isArray(historyMessages) && historyMessages.length > 0;
  let feedbackModalOpen = false;
  let isMaximized = false;
  const position = config.widget_position || "bottom-right";
  const isRight = position === "bottom-right";
  const botMessageBg = hexToRgba(config.primary_color, 0.15);

  const style = document.createElement("style");
  style.textContent = `
    .saas-widget-button {
      position: fixed;
      bottom: 20px;
      ${isRight ? "right: 20px;" : "left: 20px;"}
      width: 56px;
      height: 56px;
      border: none;
      border-radius: 50%;
      background: ${config.primary_color};
      color: ${config.text_color};
      cursor: pointer;
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
      z-index: 999999;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: transform 0.2s ease, box-shadow 0.2s ease;
    }

    .saas-widget-button svg {
      width: 26px;
      height: 26px;
      display: block;
    }

    .saas-widget-button:hover {
      transform: scale(1.05);
      box-shadow: 0 6px 20px rgba(0, 0, 0, 0.25);
    }

    .saas-widget-popup {
      position: fixed;
      bottom: 90px;
      ${isRight ? "right: 20px;" : "left: 20px;"}
      width: 350px;
      height: 400px;
      background: #ffffff;
      border-radius: 22px;
      box-shadow: 0 6px 30px rgba(0, 0, 0, 0.4););
      z-index: 999998;
      display: none;
      flex-direction: column;
      overflow: hidden;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }

    .saas-widget-header-actions {
      display: flex;
      align-items: center;
      gap: 4px;
      margin-left: auto;
      flex-shrink: 0;
    }

    .saas-widget-end-chat {
      padding: 4px 10px;
      border: 1px solid rgba(255, 255, 255, 0.5);
      border-radius: 6px;
      background: transparent;
      color: ${config.text_color};
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      font-family: inherit;
      white-space: nowrap;
      transition: background 0.2s ease;
    }

    .saas-widget-end-chat:hover {
      background: rgba(255, 255, 255, 0.15);
    }

    .saas-widget-end-chat.hidden {
      display: none;
    }

    .saas-widget-modal-overlay {
      position: absolute;
      inset: 0;
      background: rgba(0, 0, 0, 0.45);
      display: none;
      align-items: center;
      justify-content: center;
      z-index: 20;
      padding: 16px;
    }

    .saas-widget-modal-overlay.open {
      display: flex;
    }

    .saas-widget-modal {
      background: #ffffff;
      border-radius: 14px;
      padding: 20px;
      width: 100%;
      max-width: 300px;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
      text-align: center;
    }

    .saas-widget-modal-title {
      font-size: 15px;
      font-weight: 600;
      color: #1a1a1a;
      margin: 0 0 8px;
      line-height: 1.4;
    }

    .saas-widget-modal-subtitle {
      font-size: 13px;
      color: #666666;
      margin: 0 0 16px;
      line-height: 1.5;
    }

    .saas-widget-modal-actions {
      display: flex;
      gap: 10px;
      justify-content: center;
    }

    .saas-widget-modal-btn {
      flex: 1;
      padding: 10px 14px;
      border-radius: 8px;
      border: none;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      font-family: inherit;
      transition: opacity 0.2s ease;
    }

    .saas-widget-modal-btn.primary {
      background: ${config.primary_color};
      color: ${config.text_color};
    }

    .saas-widget-modal-btn.secondary {
      background: #f0f0f0;
      color: #333333;
    }

    .saas-widget-modal-btn:hover:not(:disabled) {
      opacity: 0.9;
    }

    .saas-widget-modal-btn:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }

    .saas-widget-ended-state {
      display: none;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      text-align: center;
      gap: 16px;
      padding: 24px 16px;
      flex: 1;
    }

    .saas-widget-ended-state.visible {
      display: flex;
    }

    .saas-widget-ended-text {
      font-size: 14px;
      color: #484848;
      line-height: 1.5;
      margin: 0;
    }

    .saas-widget-new-chat-btn {
      padding: 10px 20px;
      border: none;
      border-radius: 8px;
      background: ${config.primary_color};
      color: ${config.text_color};
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      font-family: inherit;
      transition: opacity 0.2s ease;
    }

    .saas-widget-new-chat-btn:hover {
      opacity: 0.9;
    }

    .saas-widget-footer.hidden {
      display: none;
    }

    .saas-widget-unavailable {
      display: none;
      align-items: center;
      justify-content: center;
      flex: 1;
      padding: 24px 20px;
      text-align: center;
    }

    .saas-widget-unavailable.visible {
      display: flex;
    }

    .saas-widget-unavailable-message {
      font-size: 14px;
      line-height: 1.6;
      color: #484848;
      margin: 0;
      max-width: 280px;
    }

    .saas-widget-messages.hidden {
      display: none;
    }

    .saas-widget-popup.open {
      display: flex;
    }

    .saas-widget-popup.maximized {
      bottom: 50%;
      right: 50%;
      left: auto;
      width: 80%;
      height: 500px;
      transform: translate(50%, 50%);
    }

    .saas-widget-header {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 12px 16px;
      background: ${config.primary_color};
      color: ${config.text_color};
      flex-shrink: 0;
    }

    .saas-widget-minimize {
      width: 32px;
      height: 32px;
      padding: 0;
      border: none;
      border-radius: 6px;
      background: transparent;
      color: ${config.text_color};
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      transition: background 0.2s ease;
    }

    .saas-widget-maximize {
      width: 32px;
      height: 32px;
      padding: 0;
      border: none;
      border-radius: 6px;
      background: transparent;
      color: ${config.text_color};
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      transition: background 0.2s ease;
    }

    .saas-widget-minimize svg,
    .saas-widget-maximize svg {
      width: 18px;
      height: 18px;
      display: block;
    }

    .saas-widget-minimize:hover,
    .saas-widget-maximize:hover {
      background: rgba(255, 255, 255, 0.15);
    }

    .saas-widget-avatar {
      width: 40px;
      height: 40px;
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.2);
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }

    .saas-widget-avatar svg {
      width: 26px;
      height: 26px;
      display: block;
    }

    .saas-widget-title {
      font-size: 16px;
      font-weight: 600;
      margin: 0;
      line-height: 1.3;
    }

    .saas-widget-messages {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .saas-widget-message-wrap {
      display: flex;
      flex-direction: column;
      max-width: 85%;
      gap: 4px;
    }

    .saas-widget-message-wrap.user {
      align-self: flex-end;
      align-items: flex-end;
    }

    .saas-widget-message-wrap.bot {
      align-self: flex-start;
      align-items: flex-start;
    }

    .saas-widget-message-label {
      font-size: 12px;
      font-weight: 600;
      color: #484848;
      text-transform: capitalize;
      letter-spacing: 0.5px;
    }

    .saas-widget-message {
      padding: 6px 15px;
      border-radius: 12px;
      font-size: 14px;
      line-height: 1.5;
      word-wrap: break-word;
    }

    .saas-widget-message.bot {
      background: ${botMessageBg};
      color: ${config.primary_color};
      border-bottom-left-radius: 0px;
    }

    .saas-widget-message.user {
      background: ${config.primary_color};
      color: ${config.text_color};
      border-bottom-right-radius: 0px;
    }

    .saas-widget-message.typing {
      font-style: italic;
      color: #b0b0c0;
    }

    .saas-widget-footer {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 10px 10px 10px 0px;
      border-top: 1px solid #cccccc;
      background: #ffffff;
      flex-shrink: 0;
    }

    .saas-widget-input {
      flex: 1;
      padding: 10px 14px;
      border: 0px solid #cccc;
      border-radius: 8px;
      background: #ffffff;
      color: #000000;
      font-size: 14px;
      outline: none;
      font-family: inherit;
    }

    .saas-widget-input::placeholder {
      color:rgb(61, 61, 61);
    }

    .saas-widget-input:focus {
      border-color: ${config.primary_color};
    }

    .saas-widget-input:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }

    .saas-widget-send {
      width: 36px;
      height: 36px;
      padding: 0;
      border: none;
      border-radius: 50%;
      background: ${config.primary_color};
      color: ${config.text_color};
      cursor: pointer;
      font-family: inherit;
      flex-shrink: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: opacity 0.2s ease;
    }

    .saas-widget-send svg {
      width: 18px;
      height: 18px;
      display: block;
    }

    .saas-widget-send:hover:not(:disabled) {
      opacity: 0.9;
    }

    .saas-widget-send:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }

    .saas-widget-skip {
      padding: 8px 12px;
      border: 1px solid #cccccc;
      border-radius: 8px;
      background: #ffffff;
      color: #484848;
      font-size: 13px;
      cursor: pointer;
      font-family: inherit;
      flex-shrink: 0;
      transition: background 0.2s ease;
    }

    .saas-widget-skip:hover:not(:disabled) {
      background: #f5f5f5;
    }

    .saas-widget-skip:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }

    .saas-widget-skip.hidden {
      display: none;
    }
  `;
  document.head.appendChild(style);

  const button = document.createElement("button");
  button.className = "saas-widget-button";
  button.innerHTML = OPEN_CHAT_ICON_SVG;
  button.setAttribute("aria-label", "Open chat");
  document.body.appendChild(button);

  const popup = document.createElement("div");
  popup.className = "saas-widget-popup";

  const header = document.createElement("div");
  header.className = "saas-widget-header";

  if (config.show_avatar) {
    const avatar = document.createElement("div");
    avatar.className = "saas-widget-avatar";
    avatar.innerHTML = CHATBOT_ICON_SVG;
    header.appendChild(avatar);
  }

  const title = document.createElement("h3");
  title.className = "saas-widget-title";
  title.textContent = config.chat_title;
  header.appendChild(title);

  const headerActions = document.createElement("div");
  headerActions.className = "saas-widget-header-actions";

  const endChatButton = document.createElement("button");
  endChatButton.className = "saas-widget-end-chat hidden";
  endChatButton.type = "button";
  endChatButton.textContent = "End Chat";
  endChatButton.setAttribute("aria-label", "End chat");
  headerActions.appendChild(endChatButton);

  const maximizeButton = document.createElement("button");
  maximizeButton.className = "saas-widget-maximize";
  maximizeButton.type = "button";
  maximizeButton.innerHTML = MAXIMIZE_ICON_SVG;
  maximizeButton.setAttribute("aria-label", "Maximize chat");
  headerActions.appendChild(maximizeButton);

  const minimizeButton = document.createElement("button");
  minimizeButton.className = "saas-widget-minimize";
  minimizeButton.type = "button";
  minimizeButton.innerHTML = MINIMIZE_ICON_SVG;
  minimizeButton.setAttribute("aria-label", "Minimize chat");
  headerActions.appendChild(minimizeButton);

  header.appendChild(headerActions);

  const messages = document.createElement("div");
  messages.className = "saas-widget-messages";

  const unavailableAlert = document.createElement("div");
  unavailableAlert.className = "saas-widget-unavailable";

  const unavailableMessageEl = document.createElement("p");
  unavailableMessageEl.className = "saas-widget-unavailable-message";
  unavailableAlert.appendChild(unavailableMessageEl);

  const endedState = document.createElement("div");
  endedState.className = "saas-widget-ended-state";

  const endedText = document.createElement("p");
  endedText.className = "saas-widget-ended-text";
  endedText.textContent = THANK_YOU_FEEDBACK;

  const startNewChatButton = document.createElement("button");
  startNewChatButton.className = "saas-widget-new-chat-btn";
  startNewChatButton.type = "button";
  startNewChatButton.textContent = START_NEW_CHAT_LABEL;

  endedState.appendChild(endedText);
  endedState.appendChild(startNewChatButton);

  const modalOverlay = document.createElement("div");
  modalOverlay.className = "saas-widget-modal-overlay";

  const modal = document.createElement("div");
  modal.className = "saas-widget-modal";

  const modalTitle = document.createElement("p");
  modalTitle.className = "saas-widget-modal-title";

  const modalSubtitle = document.createElement("p");
  modalSubtitle.className = "saas-widget-modal-subtitle";

  const modalActions = document.createElement("div");
  modalActions.className = "saas-widget-modal-actions";

  modal.appendChild(modalTitle);
  modal.appendChild(modalSubtitle);
  modal.appendChild(modalActions);
  modalOverlay.appendChild(modal);

  const footer = document.createElement("div");
  footer.className = "saas-widget-footer";

  const input = document.createElement("input");
  input.className = "saas-widget-input";
  input.type = "text";
  input.placeholder = "Type your message...";

  const skipButton = document.createElement("button");
  skipButton.className = "saas-widget-skip hidden";
  skipButton.type = "button";
  skipButton.textContent = "Skip";
  skipButton.setAttribute("aria-label", "Skip this step");

  const sendButton = document.createElement("button");
  sendButton.className = "saas-widget-send";
  sendButton.type = "button";
  sendButton.innerHTML = SEND_ICON_SVG;
  sendButton.setAttribute("aria-label", "Send message");

  footer.appendChild(input);
  footer.appendChild(skipButton);
  footer.appendChild(sendButton);

  popup.appendChild(header);
  popup.appendChild(messages);
  popup.appendChild(unavailableAlert);
  popup.appendChild(endedState);
  popup.appendChild(footer);
  popup.appendChild(modalOverlay);
  document.body.appendChild(popup);

  let isOpen = false;
  let isSending = false;

  function setMaximized(maximized) {
    isMaximized = maximized;
    popup.classList.toggle("maximized", isMaximized);
    maximizeButton.innerHTML = isMaximized ? RESTORE_ICON_SVG : MAXIMIZE_ICON_SVG;
    maximizeButton.setAttribute(
      "aria-label",
      isMaximized ? "Restore chat" : "Maximize chat"
    );
  }

  function scrollToBottom() {
    messages.scrollTop = messages.scrollHeight;
  }

  function createMessageWrap(sender, messageClass) {
    const wrap = document.createElement("div");
    wrap.className = `saas-widget-message-wrap ${messageClass}`;

    const label = document.createElement("div");
    label.className = "saas-widget-message-label";
    label.textContent = sender;

    const bubble = document.createElement("div");
    bubble.className = `saas-widget-message ${messageClass}`;

    wrap.appendChild(label);
    wrap.appendChild(bubble);

    return { wrap, bubble };
  }

  function addUserMessage(message) {
    const { wrap, bubble } = createMessageWrap("You", "user");
    bubble.textContent = message;
    messages.appendChild(wrap);
    scrollToBottom();
  }

  function addBotMessage(message) {
    const { wrap, bubble } = createMessageWrap("AI", "bot");
    bubble.textContent = message;
    messages.appendChild(wrap);
    scrollToBottom();
    return wrap;
  }

  function showTypingIndicator() {
    const { wrap, bubble } = createMessageWrap("AI", "bot");
    bubble.classList.add("typing");
    bubble.textContent = "Typing...";
    messages.appendChild(wrap);
    scrollToBottom();
    return wrap;
  }

  function setSendingState(sending) {
    isSending = sending;
    input.disabled = sending || chatClosed || feedbackModalOpen;
    sendButton.disabled = sending || chatClosed || feedbackModalOpen;
    skipButton.disabled = sending || chatClosed || feedbackModalOpen;
  }

  function updateEndChatVisibility() {
    if (hasAiResponse && !chatClosed && onboardingComplete) {
      endChatButton.classList.remove("hidden");
    } else {
      endChatButton.classList.add("hidden");
    }
  }

  function disableChatInput() {
    input.disabled = true;
    sendButton.disabled = true;
    skipButton.disabled = true;
    footer.classList.add("hidden");
  }

  function showUnavailableState(message) {
    messages.classList.add("hidden");
    unavailableMessageEl.textContent = message;
    unavailableAlert.classList.add("visible");
    disableChatInput();
    endChatButton.classList.add("hidden");
  }

  function showChatEndedState() {
    chatClosed = true;
    feedbackModalOpen = false;
    setFeedbackPending(currentSessionId, false);
    modalOverlay.classList.remove("open");
    messages.classList.add("hidden");
    endedState.classList.add("visible");
    disableChatInput();
    endChatButton.classList.add("hidden");
  }

  function clearModalActions() {
    modalActions.innerHTML = "";
  }

  function createModalButton(label, className, onClick) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `saas-widget-modal-btn ${className}`;
    button.textContent = label;
    button.addEventListener("click", onClick);
    modalActions.appendChild(button);
    return button;
  }

  function showConfirmEndModal() {
    feedbackModalOpen = true;
    setSendingState(isSending);
    modalTitle.textContent = CHAT_END_CONFIRMATION;
    modalSubtitle.textContent = CHAT_END_CONFIRMATION_SUBTITLE;
    modalSubtitle.style.display = "block";
    clearModalActions();

    createModalButton("No", "secondary", () => {
      feedbackModalOpen = false;
      modalOverlay.classList.remove("open");
      setSendingState(isSending);
    });

    createModalButton("Yes", "primary", () => {
      setFeedbackPending(currentSessionId, true);
      showFeedbackModal();
    });

    modalOverlay.classList.add("open");
  }

  function showFeedbackModal() {
    feedbackModalOpen = true;
    disableChatInput();
    modalTitle.textContent = CHAT_FEEDBACK_QUESTION;
    modalSubtitle.style.display = "none";
    clearModalActions();

    createModalButton("No", "secondary", () => {
      submitFeedback("unresolved");
    });

    createModalButton("Yes", "primary", () => {
      submitFeedback("resolved");
    });

    modalOverlay.classList.add("open");
  }

  async function submitFeedback(resolution) {
    const buttons = modalActions.querySelectorAll("button");
    buttons.forEach((btn) => {
      btn.disabled = true;
    });

    try {
      const { response, data } = await updateChatSessionStatus(
        publicKey,
        currentSessionId,
        "closed",
        resolution
      );

      if (!response.ok || !data.success) {
        buttons.forEach((btn) => {
          btn.disabled = false;
        });
        addBotMessage(data.message || "Sorry, something went wrong.");
        return;
      }

      setFeedbackPending(currentSessionId, false);
      showChatEndedState();
    } catch (error) {
      console.error("Widget:", error);
      buttons.forEach((btn) => {
        btn.disabled = false;
      });
      addBotMessage("Sorry, something went wrong.");
    }
  }

  async function startNewChat() {
    setSendingState(true);

    try {
      const newSessionId = await startChatSession(publicKey, getStoredVisitorKey(publicKey));
      currentSessionId = newSessionId;
      setFeedbackPending(newSessionId, false);

      const freshHistory = await fetchChatHistory(newSessionId);

      chatClosed = false;
      hasAiResponse = false;
      feedbackModalOpen = false;
      visitorStep = freshHistory.visitor_step || "name";
      onboardingComplete = freshHistory.onboarding_complete !== false;
      canSkip = Boolean(freshHistory.can_skip);

      messages.innerHTML = "";
      messages.classList.remove("hidden");
      endedState.classList.remove("visible");
      footer.classList.remove("hidden");
      modalOverlay.classList.remove("open");
      input.value = "";
      endChatButton.classList.add("hidden");

      applyOnboardingState(
        visitorStep,
        freshHistory.question,
        canSkip,
        onboardingComplete
      );

      addBotMessage(config.welcome_message);
      if (!onboardingComplete && freshHistory.question) {
        addBotMessage(freshHistory.question);
      }

      setSendingState(false);
      updateEndChatVisibility();
    } catch (error) {
      console.error("Widget:", error);
      setSendingState(false);
    }
  }

  function updateSkipVisibility() {
    if (!onboardingComplete && canSkip) {
      skipButton.classList.remove("hidden");
    } else {
      skipButton.classList.add("hidden");
    }
  }

  function applyOnboardingState(step, question, skipAllowed, complete) {
    visitorStep = step;
    canSkip = skipAllowed;
    onboardingComplete = complete;
    updateSkipVisibility();

    if (!complete && question) {
      input.placeholder =
        step === "name"
          ? "Enter your name"
          : step === "email"
            ? "Enter your email"
            : step === "phone"
              ? "Enter your phone number"
              : config.input_placeholder || "Type your message...";
    } else {
      input.placeholder = config.input_placeholder || "Type your message...";
    }
  }

  async function submitVisitorInfo(value, skip = false) {
    const response = await fetch(`${API_BASE_URL}/v1/widget/visitor-info`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        session_id: currentSessionId,
        step: visitorStep,
        value: value || null,
        skip,
      }),
    });

    const data = await response.json();
    return { response, data };
  }

  async function handleOnboardingInput(message, skip = false) {
    if (!skip && !message) {
      return;
    }

    if (!skip) {
      addUserMessage(message);
    }

    input.value = "";
    setSendingState(true);

    try {
      const { response, data } = await submitVisitorInfo(message, skip);

      if (!response.ok || !data.success) {
        addBotMessage(data.message || "Please check your input and try again.");
        return;
      }

      applyOnboardingState(
        data.next_step,
        data.question,
        data.can_skip,
        data.onboarding_complete
      );

      if (data.onboarding_complete) {
        if (data.visitor_key) {
          storeVisitorKey(publicKey, data.visitor_key);
        }
        if (data.message) {
          addBotMessage(data.message);
        }
        return;
      }

      if (data.question) {
        addBotMessage(data.question);
      }
    } catch (error) {
      console.error("Widget:", error);
      addBotMessage("Sorry, something went wrong.");
    } finally {
      setSendingState(false);
    }
  }

  async function sendMessage() {
    const message = input.value.trim();
    if (!message || isSending || chatClosed || feedbackModalOpen) {
      return;
    }

    if (!onboardingComplete) {
      await handleOnboardingInput(message, false);
      return;
    }

    addUserMessage(message);
    input.value = "";
    setSendingState(true);

    const typingIndicator = config.typing_indicator ? showTypingIndicator() : null;

    try {
      let activeSessionId = currentSessionId;

      const postChat = async (activeId) =>
        fetch(`${API_BASE_URL}/v1/widget/chat`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            public_key: publicKey,
            session_id: activeId,
            message,
          }),
        });

      let response = await postChat(activeSessionId);
      let data = await response.json();

      if (
        response.status === 404 &&
        data.message === "Chat session not found"
      ) {
        if (typingIndicator) {
          typingIndicator.remove();
        }
        activeSessionId = await startChatSession(publicKey, getStoredVisitorKey(publicKey));
        currentSessionId = activeSessionId;
        const freshHistory = await fetchChatHistory(activeSessionId);
        applyOnboardingState(
          freshHistory.visitor_step,
          freshHistory.question,
          freshHistory.can_skip,
          freshHistory.onboarding_complete
        );
        if (!freshHistory.onboarding_complete && freshHistory.question) {
          addBotMessage(config.welcome_message);
          addBotMessage(freshHistory.question);
        }
        setSendingState(false);
        return;
      }

      if (typingIndicator) {
        typingIndicator.remove();
      }

      if (!response.ok || !data.success) {
        if (data.chatbot_available === false) {
          showUnavailableState(data.message || CHATBOT_UNAVAILABLE_MESSAGE);
          return;
        }
        addBotMessage(data.message || "Sorry, something went wrong.");
        return;
      }

      addBotMessage(data.answer);
      hasAiResponse = true;
      updateEndChatVisibility();
    } catch (error) {
      console.error("Widget:", error);
      if (typingIndicator) {
        typingIndicator.remove();
      }
      addBotMessage("Sorry, something went wrong.");
    } finally {
      setSendingState(false);
    }
  }

  if (chatbotUnavailable) {
    showUnavailableState(unavailableMessage);
  } else if (onboardingComplete) {
    addBotMessage(config.welcome_message);

    historyMessages.forEach((item) => {
      addUserMessage(item.user_message);
      addBotMessage(item.bot_response);
    });
  } else {
    applyOnboardingState(
      visitorStep,
      historyData.question,
      canSkip,
      onboardingComplete
    );
    addBotMessage(config.welcome_message);
    if (historyData.question) {
      addBotMessage(historyData.question);
    }
  }

  if (!chatbotUnavailable) {
    updateEndChatVisibility();

    if (chatClosed) {
      showChatEndedState();
    } else if (
      !chatClosed &&
      historyData.is_active === "active" &&
      isFeedbackPending(currentSessionId)
    ) {
      showFeedbackModal();
    }
  }

  button.addEventListener("click", () => {
    isOpen = !isOpen;
    if (!isOpen) {
      setMaximized(false);
    }
    popup.classList.toggle("open", isOpen);
    button.setAttribute("aria-label", isOpen ? "Close chat" : "Open chat");
    if (isOpen && !chatClosed && isFeedbackPending(currentSessionId)) {
      showFeedbackModal();
    }
  });

  minimizeButton.addEventListener("click", () => {
    isOpen = false;
    setMaximized(false);
    popup.classList.remove("open");
    button.setAttribute("aria-label", "Open chat");
  });

  maximizeButton.addEventListener("click", () => {
    if (!isOpen) {
      return;
    }
    setMaximized(!isMaximized);
  });

  endChatButton.addEventListener("click", () => {
    if (!chatClosed && !feedbackModalOpen && hasAiResponse) {
      showConfirmEndModal();
    }
  });

  startNewChatButton.addEventListener("click", () => {
    startNewChat();
  });

  sendButton.addEventListener("click", sendMessage);

  skipButton.addEventListener("click", () => {
    if (!onboardingComplete && canSkip && !isSending) {
      handleOnboardingInput("", true);
    }
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      sendMessage();
    }
  });
}
