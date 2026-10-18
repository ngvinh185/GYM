// =====================================================
// SUPABASE CONFIGURATION
// =====================================================
// Cấu hình kết nối tới Supabase
// Thay đổi SUPABASE_URL và SUPABASE_ANON_KEY bằng thông tin của bạn

const DEFAULT_SUPABASE_URL = "https://mcyhkfhbbckeoorhvqiu.supabase.co";
const DEFAULT_SUPABASE_ANON_KEY =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1jeWhrZmhiYmNrZW9vcmh2cWl1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTA2NjE1NTYsImV4cCI6MjEwNjIzNzU1Nn0.sIXDvONI3GP7d60BzGu_xtwS6ekFC5xB6DeRE5nsqw4";

const runtimeConfig = window.GYMHEART_SUPABASE_CONFIG || {};
const useCustomLocalConfig =
  localStorage.getItem("gymheart_use_custom_supabase") === "1";

const customLocalUrl = useCustomLocalConfig
  ? localStorage.getItem("gymheart_supabase_url")
  : null;
const customLocalAnonKey = useCustomLocalConfig
  ? localStorage.getItem("gymheart_supabase_anon_key")
  : null;

const SUPABASE_URL =
  runtimeConfig.url || customLocalUrl || DEFAULT_SUPABASE_URL;
const SUPABASE_ANON_KEY =
  runtimeConfig.anonKey || customLocalAnonKey || DEFAULT_SUPABASE_ANON_KEY;

const hasValidConfig =
  SUPABASE_URL.startsWith("https://") && SUPABASE_ANON_KEY.length > 20;

// Log để debug
console.log(
  "Initializing Supabase with URL:",
  hasValidConfig ? SUPABASE_URL : "<missing>",
);

// Check if supabase library is loaded
if (typeof window.supabase === "undefined") {
  console.error(
    "❌ Supabase library not loaded! Check CDN link or internet connection.",
  );
  alert(
    "Lỗi: Không thể tải thư viện Supabase. Vui lòng:\n1. Kiểm tra kết nối internet\n2. Kiểm tra CDN link trong <head> của HTML\n3. Thử tải lại trang",
  );
  window.supabaseClient = null;
} else if (!hasValidConfig) {
  console.error("❌ Supabase config invalid.");
  alert("Cấu hình Supabase không hợp lệ. Vui lòng kiểm tra URL và API key.");
  window.supabaseClient = null;
} else {
  try {
    // Khởi tạo Supabase client
    const supabase = window.supabase.createClient(
      SUPABASE_URL,
      SUPABASE_ANON_KEY,
    );

    // Export để sử dụng ở các file khác
    window.supabaseClient = supabase;

    console.log("✅ Supabase client initialized successfully");

    // Test connection
    supabase
      .from("users")
      .select("count", { count: "exact", head: true })
      .then(({ error }) => {
        if (error) {
          console.error("⚠️ Supabase connection test failed:", error.message);
          console.log(
            "Vui lòng kiểm tra:\n1. Supabase URL có đúng không\n2. API Key có đúng không\n3. RLS policies đã được set up chưa",
          );
        } else {
          console.log("✅ Supabase connection test successful");
        }
      });
  } catch (error) {
    console.error("❌ Error initializing Supabase:", error);
    alert("Lỗi khởi tạo Supabase: " + error.message);
    window.supabaseClient = null;
  }
}

// =====================================================
// HƯỚNG DẪN LẤY THÔNG TIN SUPABASE
// =====================================================
/*
1. Đăng nhập vào Supabase Dashboard: https://app.supabase.com
2. Chọn project của bạn
3. Vào Settings > API
4. Copy:
   - Project URL → thay vào SUPABASE_URL
   - anon/public key → thay vào SUPABASE_ANON_KEY
5. Có thể override config runtime ở console (chỉ khi bật cờ custom):
  localStorage.setItem('gymheart_use_custom_supabase', '1')
  localStorage.setItem('gymheart_supabase_url', 'https://xxx.supabase.co')
  localStorage.setItem('gymheart_supabase_anon_key', 'eyJ...')

VÍ DỤ:
const SUPABASE_URL = 'https://abcdefghijklmnop.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...';
*/
