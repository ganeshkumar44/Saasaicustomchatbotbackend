console.log("Widget Loaded");

const API_BASE_URL = "__WIDGET_API_BASE_URL__";

const chatbotKey = document.currentScript.getAttribute("data-chatbot-key");

console.log(chatbotKey);

const SESSION_STORAGE_KEY = "chat_session_id";

async function startChatSession(publicKey) {
  const response = await fetch(`${API_BASE_URL}/v1/widget/session/start`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      public_key: publicKey,
    }),
  });

  const data = await response.json();

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
  return response.ok;
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

  return startChatSession(publicKey);
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
    };
  }

  const data = await response.json();

  if (!data.success) {
    return {
      messages: [],
      visitor_step: "completed",
      question: null,
      can_skip: false,
      onboarding_complete: true,
    };
  }

  return {
    messages: Array.isArray(data.messages) ? data.messages : [],
    visitor_step: data.visitor_step || "completed",
    question: data.question || null,
    can_skip: Boolean(data.can_skip),
    onboarding_complete: data.onboarding_complete !== false,
  };
}

async function loadWidget(publicKey) {
  const sessionId = await ensureChatSession(publicKey);

  const [configResponse, historyData] = await Promise.all([
    fetch(`${API_BASE_URL}/v1/widget/config/${publicKey}`).then(async (res) => {
      if (!res.ok) {
        throw new Error("Widget configuration not found");
      }
      return res.json();
    }),
    fetchChatHistory(sessionId),
  ]);

  console.log("Chat session:", sessionId);
  console.log(configResponse);
  console.log("Chat history:", historyData);

  if (!configResponse.success || !configResponse.data) {
    return;
  }

  initWidget(configResponse.data, publicKey, sessionId, historyData);
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

function initWidget(config, publicKey, sessionId, historyData = {}) {
  let currentSessionId = sessionId;
  const historyMessages = historyData.messages || [];
  let visitorStep = historyData.visitor_step || "completed";
  let onboardingComplete = historyData.onboarding_complete !== false;
  let canSkip = Boolean(historyData.can_skip);
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

    .saas-widget-popup.open {
      display: flex;
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
      margin-left: auto;
      transition: background 0.2s ease;
    }

    .saas-widget-minimize svg {
      width: 18px;
      height: 18px;
      display: block;
    }

    .saas-widget-minimize:hover {
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

  const minimizeButton = document.createElement("button");
  minimizeButton.className = "saas-widget-minimize";
  minimizeButton.type = "button";
  minimizeButton.innerHTML = MINIMIZE_ICON_SVG;
  minimizeButton.setAttribute("aria-label", "Minimize chat");
  header.appendChild(minimizeButton);

  const messages = document.createElement("div");
  messages.className = "saas-widget-messages";

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
  popup.appendChild(footer);
  document.body.appendChild(popup);

  let isOpen = false;
  let isSending = false;

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
    input.disabled = sending;
    sendButton.disabled = sending;
    skipButton.disabled = sending;
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
    if (!message || isSending) {
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
        activeSessionId = await startChatSession(publicKey);
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
        addBotMessage("Sorry, something went wrong.");
        return;
      }

      addBotMessage(data.answer);
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

  if (onboardingComplete) {
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

  button.addEventListener("click", () => {
    isOpen = !isOpen;
    popup.classList.toggle("open", isOpen);
    button.setAttribute("aria-label", isOpen ? "Close chat" : "Open chat");
  });

  minimizeButton.addEventListener("click", () => {
    isOpen = false;
    popup.classList.remove("open");
    button.setAttribute("aria-label", "Open chat");
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
