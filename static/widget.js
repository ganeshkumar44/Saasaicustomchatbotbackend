console.log("Widget Loaded");

const API_BASE_URL = "__WIDGET_API_BASE_URL__";

const chatbotKey = document.currentScript.getAttribute("data-chatbot-key");

console.log(chatbotKey);

const SESSION_STORAGE_KEY = "chat_session_id";

async function ensureChatSession(publicKey) {
  const existingSession = localStorage.getItem(SESSION_STORAGE_KEY);
  if (existingSession) {
    return existingSession;
  }

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

async function loadWidget(publicKey) {
  const [sessionId, configResponse] = await Promise.all([
    ensureChatSession(publicKey),
    fetch(`${API_BASE_URL}/v1/widget/config/${publicKey}`).then(async (res) => {
      if (!res.ok) {
        throw new Error("Widget configuration not found");
      }
      return res.json();
    }),
  ]);

  console.log("Chat session:", sessionId);
  console.log(configResponse);

  if (!configResponse.success || !configResponse.data) {
    return;
  }

  initWidget(configResponse.data, publicKey, sessionId);
}

if (!chatbotKey) {
  console.error("Widget: missing data-chatbot-key");
} else {
  loadWidget(chatbotKey).catch((error) => {
    console.error("Widget:", error);
  });
}

function initWidget(config, publicKey, sessionId) {
  const position = config.widget_position || "bottom-right";
  const isRight = position === "bottom-right";

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
      font-size: 24px;
      cursor: pointer;
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
      z-index: 999999;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: transform 0.2s ease, box-shadow 0.2s ease;
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
      background: #1e1e2e;
      border-radius: 16px;
      box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3);
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
      padding: 16px;
      background: ${config.primary_color};
      color: ${config.text_color};
      flex-shrink: 0;
    }

    .saas-widget-avatar {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.2);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 16px;
      flex-shrink: 0;
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
      font-size: 11px;
      font-weight: 600;
      color: #8b8b9e;
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }

    .saas-widget-message {
      padding: 12px 14px;
      border-radius: 12px;
      font-size: 14px;
      line-height: 1.5;
      word-wrap: break-word;
    }

    .saas-widget-message.bot {
      background: #2d2d3f;
      color: #ffffff;
      border-bottom-left-radius: 4px;
    }

    .saas-widget-message.user {
      background: ${config.primary_color};
      color: ${config.text_color};
      border-bottom-right-radius: 4px;
    }

    .saas-widget-message.typing {
      font-style: italic;
      color: #b0b0c0;
    }

    .saas-widget-footer {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 12px 16px;
      border-top: 1px solid #2d2d3f;
      background: #1e1e2e;
      flex-shrink: 0;
    }

    .saas-widget-input {
      flex: 1;
      padding: 10px 14px;
      border: 1px solid #3d3d52;
      border-radius: 8px;
      background: #2d2d3f;
      color: #ffffff;
      font-size: 14px;
      outline: none;
      font-family: inherit;
    }

    .saas-widget-input::placeholder {
      color: #8b8b9e;
    }

    .saas-widget-input:focus {
      border-color: ${config.primary_color};
    }

    .saas-widget-input:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }

    .saas-widget-send {
      padding: 10px 16px;
      border: none;
      border-radius: 8px;
      background: ${config.primary_color};
      color: ${config.text_color};
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      font-family: inherit;
      flex-shrink: 0;
      transition: opacity 0.2s ease;
    }

    .saas-widget-send:hover:not(:disabled) {
      opacity: 0.9;
    }

    .saas-widget-send:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }
  `;
  document.head.appendChild(style);

  const button = document.createElement("button");
  button.className = "saas-widget-button";
  button.innerHTML = "💬";
  button.setAttribute("aria-label", "Open chat");
  document.body.appendChild(button);

  const popup = document.createElement("div");
  popup.className = "saas-widget-popup";

  const header = document.createElement("div");
  header.className = "saas-widget-header";

  if (config.show_avatar) {
    const avatar = document.createElement("div");
    avatar.className = "saas-widget-avatar";
    avatar.innerHTML = "🤖";
    header.appendChild(avatar);
  }

  const title = document.createElement("h3");
  title.className = "saas-widget-title";
  title.textContent = config.chat_title;
  header.appendChild(title);

  const messages = document.createElement("div");
  messages.className = "saas-widget-messages";

  const footer = document.createElement("div");
  footer.className = "saas-widget-footer";

  const input = document.createElement("input");
  input.className = "saas-widget-input";
  input.type = "text";
  input.placeholder = "Type your message...";

  const sendButton = document.createElement("button");
  sendButton.className = "saas-widget-send";
  sendButton.type = "button";
  sendButton.textContent = "Send";

  footer.appendChild(input);
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
    const { wrap, bubble } = createMessageWrap("Bot", "bot");
    bubble.textContent = message;
    messages.appendChild(wrap);
    scrollToBottom();
    return wrap;
  }

  function showTypingIndicator() {
    const { wrap, bubble } = createMessageWrap("Bot", "bot");
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
  }

  async function sendMessage() {
    const message = input.value.trim();
    if (!message || isSending) {
      return;
    }

    addUserMessage(message);
    input.value = "";
    setSendingState(true);

    const typingIndicator = config.typing_indicator ? showTypingIndicator() : null;

    try {
      const response = await fetch(`${API_BASE_URL}/v1/widget/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          public_key: publicKey,
          session_id: sessionId,
          message,
        }),
      });

      const data = await response.json();

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

  addBotMessage(config.welcome_message);

  button.addEventListener("click", () => {
    isOpen = !isOpen;
    popup.classList.toggle("open", isOpen);
    button.setAttribute("aria-label", isOpen ? "Close chat" : "Open chat");
  });

  sendButton.addEventListener("click", sendMessage);

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      sendMessage();
    }
  });
}
