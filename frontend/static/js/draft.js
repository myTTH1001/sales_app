document.addEventListener("DOMContentLoaded", loadDraftOrders);

/* ================= LOAD DRAFT ORDERS ================= */
async function loadDraftOrders() {
  const token = localStorage.getItem("token");
  const tbody = document.querySelector("table tbody");

  const res = await fetch("/api/orders/draft", {
    headers: { Authorization: "Bearer " + token }
  });

  const data = await res.json();
  tbody.innerHTML = "";

  let grandTotal = 0;

  if (data.count === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="5" class="text-center text-muted">
          Không có đơn nháp nào
        </td>
      </tr>
    `;
    return;
  }

  data.orders.forEach(order => {
    const createdAt = new Date(order.created_at + "Z");
    const vnTime = createdAt.toLocaleString("vi-VN", {
      timeZone: "Asia/Ho_Chi_Minh"
    });

    // 🔹 header đơn
    const headerRow = document.createElement("tr");
    headerRow.className = "table-secondary order-row";
    headerRow.style.cursor = "pointer";
    headerRow.innerHTML = `
      <td colspan="5">
        <strong>Đơn #${order.order_id}</strong> – Ngày tạo: ${vnTime}
      </td>
    `;
    headerRow.onclick = () => openDraftOrder(order.order_id);
    tbody.appendChild(headerRow);

    // 🔹 items
    order.items.forEach(item => {
      const itemTotal = item.price * item.quantity;
      grandTotal += itemTotal;

      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${item.product_name}</td>
        <td>${item.price.toLocaleString()} VND</td>
        <td>${item.quantity}</td>
        <td>${itemTotal.toLocaleString()} VND</td>
        <td>
          <button class="btn btn-danger btn-sm">Xóa</button>
        </td>
      `;

      row.querySelector("button").onclick = (e) =>
        deleteDraftOrder(e, order.order_id);

      tbody.appendChild(row);
    });
  });

  document.querySelector(".col-md-6.text-right strong").innerText =
    grandTotal.toLocaleString() + " VND";
}

/* ================= DELETE DRAFT ================= */
async function deleteDraftOrder(event, orderId) {
  event.stopPropagation();

  if (!confirm(`Xoá đơn nháp #${orderId}?`)) return;

  const token = localStorage.getItem("token");

  const res = await fetch(`/api/orders/draft/${orderId}`, {
    method: "DELETE",
    headers: { Authorization: "Bearer " + token }
  });

  if (!res.ok) {
    alert("Xoá đơn thất bại");
    return;
  }

  loadDraftOrders();
}

/* ================= OPEN DRAFT ================= */
async function openDraftOrder(orderId) {
  const token = localStorage.getItem("token");

  const res = await fetch(`/api/orders/${orderId}`, {
    headers: { Authorization: "Bearer " + token }
  });

  if (!res.ok) {
    alert("Không thể mở đơn hàng");
    return;
  }

  const order = await res.json();
  const cart = {};

  order.items.forEach(item => {
    cart[item.product_id] = {
      id: item.product_id,
      name: item.product_name,
      price: Number(item.price),
      qty: Number(item.quantity)
    };
  });

  localStorage.setItem("from_open_draft", "1");
  localStorage.setItem("current_order_id", order.id);
  localStorage.setItem("current_cart", JSON.stringify(cart));

  window.location.href = "/";
}
