document.addEventListener("DOMContentLoaded", loadOrderDetail);

async function loadOrderDetail() {
  const params = new URLSearchParams(window.location.search);
  const orderId = params.get("order_id");

  if (!orderId) {
    alert("Thiếu mã đơn hàng");
    return;
  }

  const token = localStorage.getItem("token");

  const res = await fetch(`/api/orders/${orderId}`, {
    headers: { Authorization: "Bearer " + token }
  });

  if (!res.ok) {
    alert("Không thể tải đơn hàng");
    return;
  }

  const order = await res.json();

  document.getElementById("order-id").innerText = `#${order.id}`;

  document.getElementById("order-status").innerText =
    order.status === "confirmed" ? "Đã bán"
    : order.status === "cancelled" ? "Đã huỷ"
    : "Nháp";

  document.getElementById("order-time").innerText =
    new Date(order.created_at + "Z")
      .toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" });

  const tbody = document.getElementById("order-items");
  let total = 0;
  tbody.innerHTML = "";

  order.items.forEach(item => {
    const itemTotal = item.price * item.quantity;
    total += itemTotal;

    tbody.innerHTML += `
      <tr>
        <td>${item.product_name}</td>
        <td class="text-center">${item.quantity}</td>
        <td class="text-end">${item.price.toLocaleString()} VND</td>
        <td class="text-end">${itemTotal.toLocaleString()} VND</td>
      </tr>
    `;
  });

  document.getElementById("order-total").innerText =
    total.toLocaleString() + " VND";
}
