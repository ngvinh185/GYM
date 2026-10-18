// =====================================================
// AUTHENTICATION HANDLERS
// =====================================================

const SESSION_DURATION_MS = 12 * 60 * 60 * 1000;
const DASHBOARD_VERSION = "20260408e";

function generateSessionToken() {
  const bytes = new Uint8Array(24);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

async function sha256Hex(input) {
  const encoder = new TextEncoder();
  const data = encoder.encode(input);
  const hash = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(hash))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

// Get supabase client
const supabaseClient = window.supabaseClient;

// Check if Supabase is initialized
if (!supabaseClient) {
  console.error("Supabase client not initialized!");
  alert(
    "Lỗi: Không thể kết nối đến server. Vui lòng kiểm tra kết nối internet và thử lại.",
  );
}

// Show alert message
function showAlert(message, type = "error") {
  const alertDiv = document.getElementById("alert-message");
  if (!alertDiv) return;

  alertDiv.classList.remove(
    "hidden",
    "bg-red-100",
    "bg-green-100",
    "bg-blue-100",
    "text-red-700",
    "text-green-700",
    "text-blue-700",
  );

  if (type === "success") {
    alertDiv.classList.add("bg-green-100", "text-green-700");
  } else if (type === "info") {
    alertDiv.classList.add("bg-blue-100", "text-blue-700");
  } else {
    alertDiv.classList.add("bg-red-100", "text-red-700");
  }

  const iconName =
    type === "success" ? "check_circle" : type === "info" ? "info" : "error";

  alertDiv.textContent = "";
  const wrapper = document.createElement("div");
  wrapper.className = "flex items-center gap-2";

  const icon = document.createElement("span");
  icon.className = "material-symbols-outlined";
  icon.textContent = iconName;

  const text = document.createElement("span");
  text.textContent = message;

  wrapper.appendChild(icon);
  wrapper.appendChild(text);
  alertDiv.appendChild(wrapper);
  alertDiv.classList.remove("hidden");

  // Auto hide after 5 seconds
  setTimeout(() => {
    alertDiv.classList.add("hidden");
  }, 5000);
}

// =====================================================
// LOGIN HANDLER
// =====================================================
document.getElementById("login-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();

  const email = document
    .getElementById("login-email")
    .value.trim()
    .toLowerCase();
  const password = document.getElementById("login-password").value;
  const btnText = document.getElementById("login-btn-text");

  // Check if supabaseClient exists
  if (!supabaseClient) {
    showAlert(
      "Lỗi: Không thể kết nối đến server. Vui lòng kiểm tra kết nối internet.",
      "error",
    );
    return;
  }

  // Show loading
  btnText.textContent = "Đang đăng nhập...";

  if (typeof bcrypt === "undefined" || !bcrypt || !bcrypt.compare) {
    showAlert(
      "Lỗi hệ thống: Không tải được bộ xác thực mật khẩu. Vui lòng tải lại trang.",
      "error",
    );
    btnText.textContent = "Đăng nhập";
    return;
  }

  try {
    // Query user from database
    const { data: users, error } = await supabaseClient
      .from("users")
      .select(
        "id, email, password_hash, full_name, phone, avatar_url, date_of_birth, gender, address, role, is_active, bio, specialization, years_of_experience, certification, requested_role, created_at, updated_at",
      )
      .eq("email", email)
      .limit(1);

    if (error) {
      console.error("Database error:", error);
      showAlert("Lỗi kết nối database: " + error.message, "error");
      btnText.textContent = "Đăng nhập";
      return;
    }

    if (!users || users.length === 0) {
      showAlert("Email hoặc mật khẩu không đúng!", "error");
      btnText.textContent = "Đăng nhập";
      return;
    }

    const user = users[0];

    if (!user.is_active) {
      showAlert(
        "Tài khoản đã bị vô hiệu hóa. Vui lòng liên hệ quản trị viên.",
        "error",
      );
      btnText.textContent = "Đăng nhập";
      return;
    }

    // Check password and auto-upgrade legacy plaintext hashes
    let passwordMatch = false;

    try {
      const hashValue = user.password_hash || "";
      const isBcryptHash = /^\$2[abxy]\$[0-9]{2}\$.{53}$/.test(hashValue);
      const isSha256Hash = /^[a-f0-9]{64}$/i.test(hashValue);

      if (isBcryptHash) {
        passwordMatch = await bcrypt.compare(password, user.password_hash);
      } else {
        // Legacy fallback: support plaintext and old SHA-256 hashes.
        if (isSha256Hash) {
          const passwordSha256 = await sha256Hex(password);
          passwordMatch = hashValue.toLowerCase() === passwordSha256;
        } else {
          passwordMatch =
            hashValue === password || hashValue.trim() === password;
        }

        if (passwordMatch) {
          const upgradedHash = await bcrypt.hash(password, 10);
          const { error: upgradeError } = await supabaseClient
            .from("users")
            .update({ password_hash: upgradedHash })
            .eq("id", user.id);

          if (upgradeError) {
            console.warn("Legacy password upgrade failed:", upgradeError);
          }
        }
      }
    } catch (error) {
      console.error("Password comparison error:", error);
      showAlert(
        "Lỗi hệ thống: Không thể xác thực mật khẩu an toàn. Vui lòng thử lại sau.",
        "error",
      );
      btnText.textContent = "Đăng nhập";
      return;
    }

    if (!passwordMatch) {
      showAlert("Email hoặc mật khẩu không đúng!", "error");
      btnText.textContent = "Đăng nhập";
      return;
    }

    // Lấy JWT thật từ backend
    const API_URL = "http://localhost:8000";
    let authData;
    try {
      const res = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      authData = await res.json();
      if (!res.ok) {
        showAlert(authData.detail || "Đăng nhập thất bại!", "error");
        btnText.textContent = "Đăng nhập";
        return;
      }
    } catch (err) {
      console.error("Backend login error:", err);
      showAlert(
        "Không kết nối được backend (cổng 8000). Hãy kiểm tra server đang chạy.",
        "error",
      );
      btnText.textContent = "Đăng nhập";
      return;
    }

    const safeUser = authData.user;
    const session = {
      token: authData.token, // JWT, bắt đầu bằng eyJ
      issuedAt: authData.issued_at,
      expiresAt: authData.expires_at,
      userId: safeUser.id,
    };

    localStorage.setItem("gymheart_user", JSON.stringify(safeUser));
    localStorage.setItem("gymheart_token", JSON.stringify(session));

    showAlert("Đăng nhập thành công! Đang chuyển hướng...", "success");

    // Redirect based on role
    setTimeout(() => {
      switch (safeUser.role) {
        case "admin":
          window.location.href = `admin-dashboard.html?v=${DASHBOARD_VERSION}`;
          break;
        case "coach":
          window.location.href = "coach-dashboard.html";
          break;
        case "user":
          window.location.href = "user-dashboard.html";
          break;
        default:
          window.location.href = "index.html";
      }
    }, 1500);
  } catch (error) {
    console.error("Login error:", error);
    showAlert("Đã xảy ra lỗi! Vui lòng thử lại.", "error");
    btnText.textContent = "Đăng nhập";
  }
});

// =====================================================
// SIGNUP HANDLER
// =====================================================
document
  .getElementById("signup-form")
  ?.addEventListener("submit", async (e) => {
    e.preventDefault();

    const fullname = document.getElementById("signup-fullname").value;
    const email = document.getElementById("signup-email").value;
    const phone = document.getElementById("signup-phone").value;
    const password = document.getElementById("signup-password").value;
    const roleSelection = document.querySelector(
      'input[name="signup-role"]:checked',
    ).value;
    const btnText = document.getElementById("signup-btn-text");

    // Check if supabaseClient exists
    if (!supabaseClient) {
      showAlert(
        "Lỗi: Không thể kết nối đến server. Vui lòng kiểm tra kết nối internet.",
        "error",
      );
      return;
    }

    // Validate
    if (password.length < 6) {
      showAlert("Mật khẩu phải có ít nhất 6 ký tự!", "error");
      return;
    }

    // Show loading
    btnText.textContent = "Đang đăng ký...";

    if (typeof bcrypt === "undefined" || !bcrypt || !bcrypt.hash) {
      showAlert(
        "Lỗi hệ thống: Không tải được bộ mã hóa mật khẩu. Vui lòng tải lại trang.",
        "error",
      );
      btnText.textContent = "Đăng ký";
      return;
    }

    try {
      // Check if email exists
      const { data: existingUser } = await supabaseClient
        .from("users")
        .select("id")
        .eq("email", email)
        .single();

      if (existingUser) {
        showAlert("Email đã được sử dụng!", "error");
        btnText.textContent = "Đăng ký";
        return;
      }

      // Hash password with bcrypt
      const hashedPassword = await bcrypt.hash(password, 10);

      // Insert new user with hashed password
      const userData = {
        email: email,
        password_hash: hashedPassword, // Lưu bcrypt hash
        full_name: fullname,
        phone: phone,
        role: "user",
        is_active: true,
        avatar_url: `https://ui-avatars.com/api/?name=${encodeURIComponent(fullname)}&background=f42559&color=fff&size=200`,
      };

      // Chỉ thêm requested_role nếu chọn coach
      if (roleSelection === "coach") {
        userData.requested_role = "coach";
      }

      const { data: newUser, error } = await supabaseClient
        .from("users")
        .insert([userData])
        .select("id, email, full_name, role")
        .single();

      if (error) {
        console.error("Signup error:", error);
        if (error.message && error.message.includes("requested_role")) {
          showAlert(
            "Lỗi: Vui lòng chạy SQL script add_coach_requests.sql trước! Xem file COACH_REQUEST_GUIDE.md",
            "error",
          );
        } else {
          showAlert("Đăng ký thất bại! " + error.message, "error");
        }
        btnText.textContent = "Đăng ký";
        return;
      }

      // Success message based on role selection
      if (roleSelection === "coach") {
        showAlert(
          "Đăng ký thành công! Yêu cầu làm PT đã được gửi tới Admin. Vui lòng đợi phê duyệt.",
          "success",
        );
      } else {
        showAlert("Đăng ký thành công! Vui lòng đăng nhập.", "success");
      }

      // Reset form
      document.getElementById("signup-form").reset();

      // Switch to login tab after 2 seconds
      setTimeout(() => {
        switchTab("login");
        // Pre-fill email
        document.getElementById("login-email").value = email;
      }, 2000);
    } catch (error) {
      console.error("Signup error:", error);
      showAlert("Đã xảy ra lỗi! Vui lòng thử lại.", "error");
      btnText.textContent = "Đăng ký";
    }
  });

// =====================================================
// CHECK AUTHENTICATION
// =====================================================
function checkAuth() {
  const tokenRaw = localStorage.getItem("gymheart_token");
  const user = localStorage.getItem("gymheart_user");

  if (!tokenRaw || !user) {
    return null;
  }

  try {
    const parsedToken = JSON.parse(tokenRaw);
    const now = Date.now();

    if (
      !parsedToken?.token ||
      !parsedToken?.expiresAt ||
      !/^eyJ/.test(parsedToken.token) // chỉ chấp nhận JWT; token hex cũ sẽ bị xóa
    ) {
      throw new Error("Invalid token format");
    }

    if (now >= parsedToken.expiresAt) {
      localStorage.removeItem("gymheart_token");
      localStorage.removeItem("gymheart_user");
      return null;
    }

    const parsedUser = JSON.parse(user);
    if (parsedToken.userId && parsedUser?.id !== parsedToken.userId) {
      localStorage.removeItem("gymheart_token");
      localStorage.removeItem("gymheart_user");
      return null;
    }

    return parsedUser;
  } catch (_error) {
    // Cleanup legacy/corrupted token format
    localStorage.removeItem("gymheart_token");
    localStorage.removeItem("gymheart_user");
    return null;
  }
}

// Clear old session when on auth page
function clearOldSessionOnAuthPage() {
  // If we're on auth.html and user manually navigated here, clear old session
  if (window.location.pathname.includes("auth.html")) {
    // Check if there's a stored user
    const oldUser = checkAuth();
    if (oldUser) {
      // Clear the old session to allow fresh login
      localStorage.removeItem("gymheart_token");
      localStorage.removeItem("gymheart_user");
      console.log("Cleared old session for fresh login");
    }
  }
}

// Redirect if already logged in
function redirectIfAuthenticated() {
  const user = checkAuth();
  if (user && window.location.pathname.includes("auth.html")) {
    switch (user.role) {
      case "admin":
        window.location.href = `admin-dashboard.html?v=${DASHBOARD_VERSION}`;
        break;
      case "coach":
        window.location.href = "coach-dashboard.html";
        break;
      case "user":
        window.location.href = "user-dashboard.html";
        break;
    }
  }
}

// Require authentication for dashboard pages
function requireAuth() {
  const user = checkAuth();
  if (!user) {
    window.location.href = "auth.html";
    return null;
  }
  return user;
}

// Logout function
function logout() {
  localStorage.removeItem("gymheart_token");
  localStorage.removeItem("gymheart_user");
  window.location.href = "index.html";
}

// Run on page load
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    clearOldSessionOnAuthPage();
    checkSupabaseConnection();
  });
} else {
  clearOldSessionOnAuthPage();
  checkSupabaseConnection();
}

// Check Supabase connection on page load
function checkSupabaseConnection() {
  setTimeout(() => {
    if (!window.supabaseClient) {
      showAlert(
        "⚠️ Không thể kết nối đến server. Vui lòng kiểm tra:\n1. Kết nối internet\n2. Mở DevTools (F12) để xem chi tiết lỗi\n3. Thử reload lại trang",
        "error",
      );
    }
  }, 1000);
}

// Export functions
window.checkAuth = checkAuth;
window.requireAuth = requireAuth;
window.logout = logout;
window.showAlert = showAlert;
