document.addEventListener("DOMContentLoaded", () => {
  const select = document.getElementById("order-status");

  loadOrders(select.value);

  select.addEventListener("change", () => {
    loadOrders(select.value);
  });
});

async function loadOrders(status) {
  const token = localStorage.getItem("token");
  const tbody = document.getElementById("orders-body");

  tbody.innerHTML = `
    <tr>
      <td colspan="4" class="text-center text-muted">
        Đang tải dữ liệu...
      </td>
    </tr>
  `;

  const res = await fetch(`/api/orders/manage?status=${status}`, {
    headers: { Authorization: "Bearer " + token }
  });

  if (!res.ok) {
    tbody.innerHTML = `
      <tr>
        <td colspan="4" class="text-danger text-center">
          Lỗi tải đơn hàng
        </td>
      </tr>
    `;
    return;
  }

  const data = await res.json();
  tbody.innerHTML = "";

  if (data.count === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="4" class="text-center text-muted">
          Không có đơn hàng
        </td>
      </tr>
    `;
    return;
  }

  data.orders.forEach(order => {
    const time = new Date(order.created_at + "Z")
      .toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" });

    let actionBtn = `
      <button class="btn btn-sm btn-outline-primary"
              onclick="viewOrder(${order.id})">
        Xem
      </button>
    `;

    if (status === "draft") {
      actionBtn += `
        <button class="btn btn-sm btn-danger ms-2"
                onclick="deleteDraft(${order.id})">
          Xoá
        </button>
      `;
    }

    tbody.innerHTML += `
      <tr>
        <td>#${order.id}</td>
        <td>${time}</td>
        <td>${order.total.toLocaleString()} VND</td>
        <td>${actionBtn}</td>
      </tr>
    `;
  });
}

/* ===== ACTIONS ===== */

function viewOrder(orderId) {
  window.location.href = `/order_view.html?order_id=${orderId}`;
}

async function deleteDraft(orderId) {
  if (!confirm(`Xoá đơn nháp #${orderId}?`)) return;

  const token = localStorage.getItem("token");

  const res = await fetch(`/api/orders/draft/${orderId}`, {
    method: "DELETE",
    headers: { Authorization: "Bearer " + token }
  });

  if (!res.ok) {
    alert("Xoá thất bại");
    return;
  }

  loadOrders("draft");
}
