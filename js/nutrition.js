/**
 * GymHeart - Chuyên gia phân tích dinh dưỡng
 * Gửi thông tin người dùng tới POST /nutrition/menu (agent nutritionist) và hiển thị thực đơn.
 *
 * Nhúng vào user-dashboard.html SAU js/auth.js:
 *   <script src="js/nutrition.js"></script>
 *
 * Địa chỉ backend: window.GYMHEART_API_BASE (mặc định http://localhost:8000),
 * giống chat-widget.js. Token lấy từ localStorage "gymheart_token".
 */
(function () {
  const API_BASE = window.GYMHEART_API_BASE || "http://localhost:8000";
  const MENU_URL = API_BASE + "/nutrition/menu";
  const REQUEST_TIMEOUT_MS = 180000; // agent có thể gọi tool nhiều vòng nên khá lâu

  const form = document.getElementById("nutrition-form");
  if (!form) return;

  const resultEl = document.getElementById("nutrition-result");
  const errorEl = document.getElementById("nutrition-error");
  const submitBtn = document.getElementById("nutrition-submit");
  const submitText = document.getElementById("nutrition-submit-text");

  const fmtVND = (n) =>
    new Intl.NumberFormat("vi-VN").format(Math.round(n || 0)) + "đ";
  const fmt1 = (n) => (Math.round((n || 0) * 10) / 10).toString();
  const kcal = (p, c, f) => Math.round(p * 4 + c * 4 + f * 9);

  // Mọi chuỗi đến từ server đều đi qua esc() trước khi chèn vào innerHTML
  function esc(s) {
    return String(s ?? "").replace(
      /[&<>"']/g,
      (ch) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[ch],
    );
  }

  // ---- điền sẵn tuổi / giới tính từ hồ sơ (nếu có) ----
  (function prefill() {
    let user = null;
    try {
      user = typeof window.checkAuth === "function" ? window.checkAuth() : null;
    } catch {}
    if (!user) return;

    if (user.date_of_birth) {
      const dob = new Date(user.date_of_birth);
      if (!isNaN(dob)) {
        const now = new Date();
        let age = now.getFullYear() - dob.getFullYear();
        const m = now.getMonth() - dob.getMonth();
        if (m < 0 || (m === 0 && now.getDate() < dob.getDate())) age--;
        if (age >= 10 && age <= 100) form.age.value = age;
      }
    }
    const g = String(user.gender || "").toLowerCase();
    if (g === "nữ" || g === "nu" || g === "female") {
      form.querySelector('input[name="gender"][value="female"]').checked = true;
    }
  })();

  // ---- gửi yêu cầu ----
  function getToken() {
    try {
      if (typeof window.checkAuth === "function" && !window.checkAuth())
        return null;
      const t = JSON.parse(localStorage.getItem("gymheart_token") || "null");
      return t && t.token ? t.token : null;
    } catch {
      return null;
    }
  }

  function setLoading(on) {
    submitBtn.disabled = on;
    submitText.textContent = on
      ? "Đang lập thực đơn... (có thể mất 20-60 giây)"
      : "Phân tích & lập thực đơn";
  }

  function showError(msg) {
    errorEl.textContent = msg;
    errorEl.classList.remove("hidden");
  }

  function errorMessage(err) {
    if (err && err.name === "AbortError")
      return "Hệ thống phản hồi quá lâu, bạn thử lại sau một chút nhé.";
    const s = err && err.status;
    if (s === 401) return "Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại.";
    if (s === 422)
      return (
        err.detail || "Thông tin chưa hợp lệ, bạn kiểm tra lại các ô nhập."
      );
    if (s) return "Hệ thống đang gặp lỗi, bạn vui lòng thử lại sau.";
    return "Không kết nối được tới máy chủ. Hãy kiểm tra backend đang chạy.";
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorEl.classList.add("hidden");

    const token = getToken();
    if (!token) {
      showError("Bạn cần đăng nhập để dùng chức năng này.");
      return;
    }

    const fd = new FormData(form);
    const payload = {
      gender: fd.get("gender") === "male", // true = nam, false = nữ
      age: parseInt(fd.get("age"), 10),
      height: parseFloat(fd.get("height")),
      weight: parseFloat(fd.get("weight")),
      activity_factor: parseFloat(fd.get("activity_factor")),
      count_meal: parseInt(fd.get("count_meal"), 10),
      goal: fd.get("goal"),
      budget: parseFloat(fd.get("budget")),
    };

    setLoading(true);
    resultEl.classList.add("hidden");

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    try {
      const res = await fetch(MENU_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer " + token,
        },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
      if (!res.ok) {
        const err = new Error("HTTP " + res.status);
        err.status = res.status;
        try {
          const body = await res.json();
          // 422 từ app.py trả detail dạng chuỗi; 422 của pydantic trả mảng
          if (typeof body.detail === "string") err.detail = body.detail;
        } catch {}
        throw err;
      }
      renderResult(await res.json());
    } catch (err) {
      console.error("Nutrition error:", err);
      showError(errorMessage(err));
    } finally {
      clearTimeout(timer);
      setLoading(false);
    }
  });

  // ---- hiển thị kết quả ----
  function macroCard(label, value, unit, diff) {
    const diffTxt =
      diff === undefined || diff === null
        ? ""
        : `<p class="text-xs mt-1 ${Math.abs(diff) < 0.05 ? "text-green-600" : "text-[#9c495e]"}">${diff > 0 ? "+" : ""}${fmt1(diff)}${unit} so với mục tiêu</p>`;
    return `
      <div class="bg-white rounded-xl border border-pink-100 p-4 text-center">
        <p class="text-xs text-[#9c495e] mb-1">${esc(label)}</p>
        <p class="text-2xl font-black text-primary">${esc(value)}<span class="text-sm font-semibold text-[#9c495e]"> ${esc(unit)}</span></p>
        ${diffTxt}
      </div>`;
  }

  function renderResult(r) {
    const day = r.tong_ngay || {};
    const cmp = r.so_voi_muc_tieu || {};
    const errors = Array.isArray(r.loi) ? r.loi : [];

    const ok = !!r.dat_muc_tieu;
    const reasons = [];
    if (!r.dat_sai_so_ngay)
      reasons.push("macro cả ngày còn lệch so với mục tiêu");
    if (!r.trong_ngan_sach) reasons.push("vượt ngân sách");
    errors.forEach((x) => reasons.push(x));

    const banner = ok
      ? `<div class="rounded-xl bg-green-50 border border-green-200 text-green-800 p-4 flex items-start gap-3">
           <span class="material-symbols-outlined">check_circle</span>
           <div><p class="font-bold">Thực đơn đạt mục tiêu</p>
           <p class="text-sm">Macro cả ngày nằm trong sai số cho phép và không vượt ngân sách.</p></div>
         </div>`
      : `<div class="rounded-xl bg-amber-50 border border-amber-200 text-amber-800 p-4 flex items-start gap-3">
           <span class="material-symbols-outlined">info</span>
           <div><p class="font-bold">Thực đơn gần đạt mục tiêu</p>
           <p class="text-sm">${esc(reasons.join("; ") || "Chưa đạt toàn bộ tiêu chí.")}. Bạn có thể bấm lập lại để có thực đơn khác.</p></div>
         </div>`;

    const dayCards = [
      macroCard(
        "Năng lượng",
        kcal(day.protein_g, day.carb_g, day.fat_g),
        "kcal",
      ),
      macroCard("Protein", fmt1(day.protein_g), "g", cmp.protein_chenh_lech_g),
      macroCard("Carb", fmt1(day.carb_g), "g", cmp.carb_chenh_lech_g),
      macroCard("Fat", fmt1(day.fat_g), "g", cmp.fat_chenh_lech_g),
    ].join("");

    const budgetLeft = cmp.con_du_ngan_sach_vnd;
    const costCard = `
      <div class="bg-white rounded-xl border border-pink-100 p-4 text-center">
        <p class="text-xs text-[#9c495e] mb-1">Chi phí cả ngày</p>
        <p class="text-2xl font-black text-primary">${esc(fmtVND(day.chi_phi_vnd))}</p>
        <p class="text-xs mt-1 ${budgetLeft >= 0 ? "text-green-600" : "text-red-600"}">
          ${budgetLeft >= 0 ? "Còn dư " + esc(fmtVND(budgetLeft)) : "Vượt " + esc(fmtVND(-budgetLeft))}
        </p>
      </div>`;

    const meals = (r.bua_an || [])
      .map((m) => {
        const t = m.tong_bua || {};
        const rows = (m.mon_an || [])
          .map(
            (it) => `
            <tr class="border-t border-pink-50">
              <td class="py-2 pr-3 font-medium">${esc(it.ten)}</td>
              <td class="py-2 px-2 text-right whitespace-nowrap">${esc(fmt1(it.gram))} g</td>
              <td class="py-2 px-2 text-right">${esc(fmt1(it.protein_g))}</td>
              <td class="py-2 px-2 text-right">${esc(fmt1(it.carb_g))}</td>
              <td class="py-2 px-2 text-right">${esc(fmt1(it.fat_g))}</td>
              <td class="py-2 pl-2 text-right whitespace-nowrap">${esc(fmtVND(it.gia_vnd))}</td>
            </tr>`,
          )
          .join("");
        const badge =
          m.dat_sai_so === false
            ? '<span class="text-xs bg-amber-100 text-amber-800 px-2 py-1 rounded-full font-semibold">Lệch mục tiêu bữa</span>'
            : '<span class="text-xs bg-green-100 text-green-800 px-2 py-1 rounded-full font-semibold">Đạt mục tiêu bữa</span>';
        return `
          <div class="bg-white rounded-xl border border-pink-100 shadow-sm p-5">
            <div class="flex items-center justify-between mb-3">
              <h4 class="text-lg font-bold">Bữa ${esc(m.bua)}</h4>${badge}
            </div>
            <div class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead>
                  <tr class="text-xs text-[#9c495e] text-right">
                    <th class="text-left font-semibold pb-2">Món</th>
                    <th class="font-semibold pb-2 px-2">Khối lượng</th>
                    <th class="font-semibold pb-2 px-2">Protein</th>
                    <th class="font-semibold pb-2 px-2">Carb</th>
                    <th class="font-semibold pb-2 px-2">Fat</th>
                    <th class="font-semibold pb-2 pl-2">Giá</th>
                  </tr>
                </thead>
                <tbody>${rows}</tbody>
                <tfoot>
                  <tr class="border-t-2 border-pink-100 font-bold">
                    <td class="pt-2">Tổng bữa</td><td></td>
                    <td class="pt-2 px-2 text-right">${esc(fmt1(t.protein_g))}</td>
                    <td class="pt-2 px-2 text-right">${esc(fmt1(t.carb_g))}</td>
                    <td class="pt-2 px-2 text-right">${esc(fmt1(t.fat_g))}</td>
                    <td class="pt-2 pl-2 text-right whitespace-nowrap">${esc(fmtVND(t.chi_phi_vnd))}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>`;
      })
      .join("");

    const note = r.ghi_chu
      ? `<div class="bg-pink-50 rounded-xl p-4 text-sm text-[#5c3d44]"><p class="font-bold mb-1">Ghi chú từ chuyên gia</p><p class="whitespace-pre-wrap">${esc(r.ghi_chu)}</p></div>`
      : "";

    resultEl.innerHTML = `
      <div class="space-y-5">
        ${banner}
        <div class="grid grid-cols-2 lg:grid-cols-5 gap-3">${dayCards}${costCard}</div>
        <div class="space-y-4">${meals}</div>
        ${note}
      </div>`;
    resultEl.classList.remove("hidden");
    resultEl.scrollIntoView({ behavior: "smooth", block: "start" });
  }
})();
