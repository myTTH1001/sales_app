async function apiFetch(url, options = {}) {
  const token = localStorage.getItem("token");

  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: "Bearer " + token,
      ...(options.headers || {})
    }
  });

  // 🔥 HANDLE 401 Ở ĐÂY
  if (res.status === 401) {
    localStorage.removeItem("token");
    alert("Phiên đăng nhập đã hết hạn!");
    window.location.href = "/login.html";
    return;
  }

  return res;
}