/* ========= AUTH & USER ========= */

function parseJwt(token) {
  try {
    const base64Url = token.split(".")[1];
    const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(base64));
  } catch (err) {
    return null;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const token = localStorage.getItem("token");

  // 🔒 Chưa đăng nhập
  if (!token) {
    window.location.href = "/login.html";
    return;
  }

  const payload = parseJwt(token);

  // 🔒 Token lỗi / hết hạn
  if (!payload || !payload.sub) {
    localStorage.removeItem("token");
    window.location.href = "/login.html";
    return;
  }

  // 👤 Hiển thị username
  const usernameEl = document.getElementById("username-text");
  if (usernameEl) {
    usernameEl.innerText = " Xin chào, " + payload.sub;
  }

  // 🚪 Logout
  const logoutBtn = document.getElementById("user-action");
  if (logoutBtn) {
    logoutBtn.onclick = () => {
      if (confirm("Bạn muốn đăng xuất?")) {
        localStorage.removeItem("token");
        window.location.href = "/login.html";
      }
    };
  }
});
