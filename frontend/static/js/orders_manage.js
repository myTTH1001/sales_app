let currentPage = 1;
const limit = 10;

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("btn-filter").onclick = () => {
    currentPage = 1;
    loadOrders();
  };

  loadOrders();
});

async function loadOrders(page = currentPage) {
  currentPage = page;

  const token = localStorage.getItem("token");
  const status = document.getElementById("order-status").value;
  const dateFrom = document.getElementById("date-from").value;
  const dateTo = document.getElementById("date-to").value;

  const tbody = document.getElementById("orders-body");
  const pagination = document.getElementById("pagination");

  tbody.innerHTML = `
    <tr>
      <td colspan="5" class="text-center text-muted py-4">
        Đang tải dữ liệu...
      </td>
    </tr>
  `;

  let url = `/api/orders/manage?status=${status}&page=${page}&limit=${limit}`;

  if (dateFrom) url += `&date_from=${dateFrom}`;
  if (dateTo) url += `&date_to=${dateTo}`;

  const res = await fetch(url, {
    headers: { Authorization: "Bearer " + token }
  });

  if (!res.ok) {
    tbody.innerHTML = `
      <tr>
        <td colspan="5" class="text-center text-danger">
          Lỗi tải dữ liệu
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
        <td colspan="5" class="text-center text-muted py-4">
          Không có đơn hàng
        </td>
      </tr>
    `;
    pagination.innerHTML = "";
    return;
  }

  data.orders.forEach(order => {
    const time = new Date(order.created_at + "Z")
      .toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" });

    const statusBadge =
      order.status === "confirmed"
        ? `<span class="badge bg-success">Đã bán</span>`
        : order.status === "cancelled"
        ? `<span class="badge bg-secondary">Đã huỷ</span>`
        : `<span class="badge bg-warning text-dark">Nháp</span>`;

    tbody.innerHTML += `
      <tr>
        <td>#${order.id}</td>
        <td>${time}</td>
        <td class="text-end">${order.total.toLocaleString()} VND</td>
        <td class="text-center">${statusBadge}</td>
        <td class="text-center">
          <button class="btn btn-sm btn-outline-primary"
            onclick="viewOrder(${order.id})">
            <i class="bi bi-eye"></i>
          </button>
        </td>
      </tr>
    `;
  });

  renderPagination(data.total_pages);
}

function renderPagination(totalPages) {
  const pagination = document.getElementById("pagination");

  pagination.innerHTML = "";

  if (!totalPages || totalPages <= 1) return;

  // Nút lùi
  pagination.innerHTML += `
    <li class="page-item ${currentPage === 1 ? "disabled" : ""}">
      <a class="page-link" href="#" onclick="loadOrders(${currentPage - 1})">
        &laquo;
      </a>
    </li>
  `;

  // Các trang
  for (let i = 1; i <= totalPages; i++) {
    pagination.innerHTML += `
      <li class="page-item ${i === currentPage ? "active" : ""}">
        <a class="page-link" href="#" onclick="loadOrders(${i})">
          ${i}
        </a>
      </li>
    `;
  }

  // Nút tới
  pagination.innerHTML += `
    <li class="page-item ${currentPage === totalPages ? "disabled" : ""}">
      <a class="page-link" href="#" onclick="loadOrders(${currentPage + 1})">
        &raquo;
      </a>
    </li>
  `;
}


function viewOrder(orderId) {
  window.location.href = `/order_view.html?order_id=${orderId}`;
}
