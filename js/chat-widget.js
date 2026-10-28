/**
 * GymHeart Chat Widget
 * Nhúng vào cuối <body> của mọi trang, SAU khi đã load js/auth.js:
 *   <script src="js/chat-widget.js"></script>
 *
 * Đổi địa chỉ backend khi deploy: đặt trước thẻ script này
 *   <script>window.GYMHEART_API_BASE = "https://api.ten-mien-cua-ban.com";</script>
 * (không đặt thì mặc định http://localhost:8001).
 *
 * Token lấy từ localStorage "gymheart_token" do FastAPI cấp qua /auth/login.
 * Markdown (bảng, in đậm, danh sách) được render bằng marked + DOMPurify,
 * tự tải từ cdnjs; tải lỗi thì hiện chữ thường, widget vẫn dùng bình thường.
 */
(function () {
  const API_BASE = window.GYMHEART_API_BASE || "http://localhost:8001";
  const CHAT_API_URL = API_BASE + "/chat";
  const REQUEST_TIMEOUT_MS = 90000; // lần chat đầu server có thể chậm vì tải model
  const MAX_INPUT_LEN = 4000; // khớp giới hạn của backend
  const MAX_SAVED_MSGS = 60; // số tin tối đa lưu để dựng lại khi đổi trang
  const STATE_KEY = "gh_chat_state";

  // ---- style: theo đúng theme GymHeart (primary #203a30, font Lexend) ----
  const css = `
    #gh-chat-btn {
      position: fixed; right: 24px; bottom: 24px; width: 56px; height: 56px;
      border-radius: 9999px; border: none; background: #203a30; color: #fff;
      font-size: 26px; cursor: pointer; box-shadow: 0 4px 14px rgba(32,58,48,.28);
      z-index: 9999; display: flex; align-items: center; justify-content: center;
      transition: transform .15s ease;
    }
    #gh-chat-btn:hover { transform: scale(1.06); }
    #gh-chat-box {
      position: fixed; right: 24px; bottom: 92px; width: 340px; max-width: calc(100vw - 32px);
      height: 480px; max-height: calc(100vh - 140px); display: none; flex-direction: column;
      background: #f5f4ed; border-radius: 0.75rem; overflow: hidden; z-index: 9999;
      box-shadow: 0 10px 30px rgba(0,0,0,.18); font-family: "Lexend", sans-serif;
      border: 1px solid #cbd5ce;
    }
    #gh-chat-head {
      background: #203a30; color: #fff; padding: 14px 16px; font-weight: 600;
      display: flex; align-items: center; justify-content: space-between; font-size: 15px;
    }
    #gh-chat-head button {
      background: transparent !important; border: none; color: #fff; font-size: 20px; cursor: pointer; line-height: 1;
    }
    #gh-chat-head button:hover, #gh-chat-head button:focus-visible { background: transparent !important; color: #fff !important; }
    #gh-chat-msgs { flex: 1; overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 8px; }
    .gh-msg { max-width: 82%; padding: 9px 13px; border-radius: 0.75rem; white-space: pre-wrap;
      font-size: 13.5px; line-height: 1.45; overflow-wrap: anywhere; }
    .gh-msg.user { align-self: flex-end; background: #203a30; color: #fff; border-bottom-right-radius: 4px; }
    .gh-msg.bot { align-self: flex-start; background: #fff; color: #203a30; border: 1px solid #cbd5ce;
      border-bottom-left-radius: 4px; }

    /* nội dung markdown trong tin nhắn của bot */
    .gh-msg.bot.md { white-space: normal; max-width: 92%; }
    .gh-msg.bot.md > :first-child { margin-top: 0; }
    .gh-msg.bot.md > :last-child { margin-bottom: 0; }
    .gh-msg.bot.md p { margin: 0 0 6px; }
    .gh-msg.bot.md ul, .gh-msg.bot.md ol { margin: 4px 0 6px; padding-left: 18px; }
    .gh-msg.bot.md li { margin: 2px 0; }
    .gh-msg.bot.md a { color: #203a30; text-decoration: underline; }
    .gh-msg.bot.md code { background: rgba(244,37,89,.08); padding: 1px 4px; border-radius: 4px; font-size: 12.5px; }
    .gh-msg.bot.md table { display: block; max-width: 100%; overflow-x: auto; border-collapse: collapse; margin: 6px 0; }
    .gh-msg.bot.md th, .gh-msg.bot.md td { border: 1px solid #cbd5ce; padding: 4px 8px;
      font-size: 12.5px; text-align: left; white-space: nowrap; }
    .gh-msg.bot.md th { background: #e8eee8; font-weight: 600; }

    #gh-chat-form { display: flex; border-top: 1px solid #cbd5ce; background: #fff; }
    #gh-chat-in { flex: 1; border: none; padding: 12px 14px; outline: none; font-family: inherit;
      font-size: 13.5px; background: transparent; color: #203a30; }
    #gh-chat-form button.send { border: none; background: none; color: #203a30; padding: 0 16px;
      cursor: pointer; font-weight: 600; font-size: 13.5px; }
    #gh-chat-form button.send:disabled { opacity: .4; cursor: default; }

    @media (prefers-color-scheme: dark) {
      #gh-chat-box { background: #221014; border-color: #3a1f27; }
      .gh-msg.bot { background: #2c1319; color: #f6e4e8; border-color: #3a1f27; }
      .gh-msg.bot.md th, .gh-msg.bot.md td { border-color: #4a2631; }
      .gh-msg.bot.md th { background: #3a1f27; }
      #gh-chat-form { background: #2c1319; border-color: #3a1f27; }
      #gh-chat-in { color: #f6e4e8; }
    }
  `;
  const styleTag = document.createElement("style");
  styleTag.textContent = css;
  document.head.appendChild(styleTag);

  // ---- DOM ----
  const btn = document.createElement("button");
  btn.id = "gh-chat-btn";
  btn.setAttribute("aria-label", "Mở trợ lý GymHeart");
  btn.textContent = "💬";

  const box = document.createElement("div");
  box.id = "gh-chat-box";
  box.innerHTML = `
    <div id="gh-chat-head">
      <span>🏋️ Trợ lý GymHeart</span>
      <button id="gh-chat-close" aria-label="Đóng">✕</button>
    </div>
    <div id="gh-chat-msgs" role="log" aria-live="polite"></div>
    <form id="gh-chat-form">
      <input id="gh-chat-in" maxlength="${MAX_INPUT_LEN}" placeholder="Hỏi về khóa học, lịch tập..." autocomplete="off" />
      <button type="submit" class="send">Gửi</button>
    </form>
  `;

  document.body.appendChild(btn);
  document.body.appendChild(box);

  const msgsEl = box.querySelector("#gh-chat-msgs");
  const inputEl = box.querySelector("#gh-chat-in");
  const formEl = box.querySelector("#gh-chat-form");
  const sendBtn = formEl.querySelector("button.send");

  // ---- render markdown an toàn (marked + DOMPurify, tải từ cdnjs) ----
  const PURIFY_OPTIONS = {
    FORBID_TAGS: ["img", "style", "form", "input", "button", "iframe"],
    FORBID_ATTR: ["style"],
  };

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = src;
      s.async = true;
      s.onload = resolve;
      s.onerror = () => reject(new Error("Không tải được " + src));
      document.head.appendChild(s);
    });
  }

  function loadMarkdownLibs() {
    const jobs = [];
    if (!window.marked) {
      jobs.push(
        loadScript(
          "https://cdnjs.cloudflare.com/ajax/libs/marked/12.0.2/marked.min.js",
        ),
      );
    }
    if (!window.DOMPurify) {
      jobs.push(
        loadScript(
          "https://cdnjs.cloudflare.com/ajax/libs/dompurify/3.1.6/purify.min.js",
        ),
      );
    }
    return Promise.all(jobs).then(() => {
      if (window.DOMPurify) {
        // link trong tin nhắn luôn mở tab mới
        window.DOMPurify.addHook("afterSanitizeAttributes", (node) => {
          if (node.tagName === "A") {
            node.setAttribute("target", "_blank");
            node.setAttribute("rel", "noopener noreferrer");
          }
        });
      }
    });
  }

  function renderBot(el, text) {
    el._raw = text; // giữ bản gốc để render lại khi thư viện tải xong
    if (window.marked && window.DOMPurify) {
      try {
        const html = window.marked.parse(text, { gfm: true, breaks: true });
        el.classList.add("md");
        el.innerHTML = window.DOMPurify.sanitize(html, PURIFY_OPTIONS);
        return;
      } catch (e) {
        console.error("Markdown render error:", e);
      }
    }
    el.classList.remove("md");
    el.textContent = text; // textContent: không bao giờ chạy HTML từ server
  }

  // Tin của user luôn là textContent. Chỉ tin của bot mới qua markdown + sanitize.
  function setContent(el, text, who) {
    if (who === "bot") renderBot(el, text);
    else el.textContent = text;
  }

  // ---- trạng thái hội thoại (theo tab, theo user) ----
  let state = null; // { uid, sessionId, msgs: [{who, text}] }

  function newSessionId() {
    return crypto.randomUUID
      ? crypto.randomUUID()
      : String(Date.now()) + Math.random().toString(36).slice(2);
  }

  function loadState() {
    try {
      const s = JSON.parse(sessionStorage.getItem(STATE_KEY) || "null");
      if (s && s.sessionId && Array.isArray(s.msgs)) return s;
    } catch {}
    return null;
  }

  function saveState() {
    try {
      sessionStorage.setItem(STATE_KEY, JSON.stringify(state));
    } catch {}
  }

  function remember(who, text) {
    state.msgs.push({ who, text });
    if (state.msgs.length > MAX_SAVED_MSGS) {
      state.msgs.splice(0, state.msgs.length - MAX_SAVED_MSGS);
    }
    saveState();
  }

  // ---- đăng nhập: dùng checkAuth() của auth.js, token do FastAPI cấp ----
  function getCurrentUser() {
    try {
      return typeof window.checkAuth === "function" ? window.checkAuth() : null;
    } catch {
      return null;
    }
  }

  function userKey(user) {
    return user ? String(user.id || user.email || "user") : null;
  }

  function getAccessToken() {
    if (!getCurrentUser()) return null; // checkAuth() đã xoá token nếu hết hạn
    try {
      const t = JSON.parse(localStorage.getItem("gymheart_token") || "null");
      return t && t.token ? t.token : null;
    } catch {
      return null;
    }
  }

  // ---- hiển thị tin nhắn ----
  function addMsg(text, who, save) {
    const d = document.createElement("div");
    d.className = "gh-msg " + who;
    setContent(d, text, who);
    msgsEl.appendChild(d);
    msgsEl.scrollTop = msgsEl.scrollHeight;
    if (save) remember(who, text);
    return d;
  }

  function greet() {
    const user = getCurrentUser();
    addMsg(
      user
        ? `Chào ${(user.full_name || "bạn").split(" ").pop()}! Mình có thể giúp gì cho bạn?`
        : "Xin chào! Mình là trợ lý GymHeart. Vui lòng đăng nhập để dùng trợ lý nhé.",
      "bot",
      false,
    );
  }

  function renderAll() {
    msgsEl.innerHTML = "";
    greet();
    state.msgs.forEach((m) => addMsg(m.text, m.who, false));
  }

  // Đổi tài khoản (đăng xuất/đăng nhập cùng tab) thì bắt đầu hội thoại mới,
  // để không hiện lịch sử của người trước.
  function syncUser(force) {
    const uid = userKey(getCurrentUser());
    const changed = !state || state.uid !== uid;
    if (changed) {
      state = { uid, sessionId: newSessionId(), msgs: [] };
      saveState();
    }
    if (changed || force) renderAll();
  }

  state = loadState();
  syncUser(true);

  // thư viện markdown tải xong thì render lại các tin của bot đã hiện
  loadMarkdownLibs()
    .then(() => {
      msgsEl.querySelectorAll(".gh-msg.bot").forEach((el) => {
        if (el._raw) renderBot(el, el._raw);
      });
    })
    .catch((err) =>
      console.warn("Chat widget: không render được markdown:", err),
    );

  // ---- mở / đóng ----
  btn.addEventListener("click", () => {
    const opening = box.style.display !== "flex";
    box.style.display = opening ? "flex" : "none";
    if (opening) {
      syncUser(false);
      inputEl.focus();
    }
  });
  box.querySelector("#gh-chat-close").addEventListener("click", () => {
    box.style.display = "none";
  });

  // ---- gửi tin ----
  function errorMessage(err) {
    if (err && err.name === "AbortError") {
      return "Mình trả lời hơi lâu, bạn vui lòng thử lại sau một chút nhé.";
    }
    const status = err && err.status;
    if (status === 401)
      return "Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại.";
    if (status === 422)
      return "Tin nhắn không hợp lệ hoặc quá dài, bạn thử viết ngắn lại nhé.";
    if (status) return "Hệ thống đang gặp lỗi, bạn vui lòng thử lại sau.";
    return "Xin lỗi, mình chưa kết nối được tới máy chủ. Vui lòng thử lại sau.";
  }

  formEl.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = inputEl.value.trim();
    if (!text) return;

    syncUser(false);

    const token = getAccessToken();
    if (!token) {
      addMsg("Bạn cần đăng nhập để dùng trợ lý.", "bot", false);
      return;
    }

    inputEl.value = "";
    sendBtn.disabled = true;
    addMsg(text, "user", true);
    const loading = addMsg("Đang trả lời...", "bot", false);

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

    try {
      const res = await fetch(CHAT_API_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer " + token,
        },
        // KHÔNG gửi user_id/role: server tự lấy từ token
        body: JSON.stringify({ message: text, session_id: state.sessionId }),
        signal: controller.signal,
      });
      if (!res.ok) {
        const err = new Error("HTTP " + res.status);
        err.status = res.status;
        throw err;
      }
      const data = await res.json();
      setContent(loading, data.reply, "bot");
      remember("bot", data.reply);
    } catch (err) {
      setContent(loading, errorMessage(err), "bot"); // tin lỗi không lưu vào lịch sử
      console.error("Chat widget error:", err);
    } finally {
      clearTimeout(timer);
      sendBtn.disabled = false;
      msgsEl.scrollTop = msgsEl.scrollHeight;
    }
  });
})();
