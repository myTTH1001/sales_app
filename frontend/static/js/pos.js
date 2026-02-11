/* ================= POS STATE ================= */
let products = [];
let cart = {};

/* ================= LOAD PRODUCTS ================= */
async function loadProducts() {
  const res = await fetch("/api/products/", {
    headers: {
      Authorization: "Bearer " + localStorage.getItem("token")
    }
  });

  products = await res.json();
  renderProducts(products);
}

/* ================= RENDER PRODUCTS ================= */
function renderProducts(list) {
  const container = document.getElementById("pos-product-list");
  if (!container) return;

  container.innerHTML = "";

  list.forEach(p => {
    container.innerHTML += `
      <div class="col-6 col-lg-4 mb-3">
        <div class="card h-100 pos-product" data-id="${p.id}">
          <img src="${p.image || "/static/images/no_image.png"}"
               class="card-img-top"
               style="height:130px;object-fit:cover">
          <div class="card-body text-center p-2">
            <div class="font-weight-bold small">${p.name}</div>
            <div class="text-danger font-weight-bold">
              ${Number(p.price).toLocaleString()} VNĐ
            </div>
          </div>
        </div>
      </div>
    `;
  });

  // click sản phẩm
  document.querySelectorAll(".pos-product").forEach(el => {
    el.onclick = () => addToCart(Number(el.dataset.id));
  });
}

/* ================= CART ================= */
function addToCart(id) {
  const p = products.find(x => x.id === id);
  if (!p) return;

  if (!cart[id]) cart[id] = { ...p, qty: 1 };
  else cart[id].qty++;

  renderCart();
}

function changeQty(id, delta) {
  if (!cart[id]) return;

  cart[id].qty += delta;
  if (cart[id].qty <= 0) delete cart[id];

  renderCart();
}

function removeItem(id) {
  delete cart[id];
  renderCart();
}

function renderCart() {
  const container = document.getElementById("cart-items");
  if (!container) return;

  container.innerHTML = "";
  let total = 0;
  const items = Object.values(cart);

  if (items.length === 0) {
    container.innerHTML =
      `<p class="text-muted text-center">Chưa có sản phẩm</p>`;
  }

  items.forEach(item => {
    total += item.price * item.qty;

    container.innerHTML += `
      <div class="border-bottom pb-2 mb-2">
        <div class="font-weight-bold small">${item.name}</div>

        <div class="d-flex justify-content-between align-items-center mt-1">
          <div class="btn-group btn-group-sm">
            <button class="btn btn-outline-secondary"
                    onclick="changeQty(${item.id}, -1)">−</button>
            <button class="btn btn-light" disabled>${item.qty}</button>
            <button class="btn btn-outline-secondary"
                    onclick="changeQty(${item.id}, 1)">+</button>
          </div>

          <div class="text-right">
            <div class="small text-danger font-weight-bold">
              ${(item.price * item.qty).toLocaleString()} VNĐ
            </div>
            <button class="btn btn-sm btn-link text-danger p-0"
                    onclick="removeItem(${item.id})">❌ xoá</button>
          </div>
        </div>
      </div>
    `;
  });

  document.getElementById("cart-total").innerText =
    total.toLocaleString() + " VNĐ";

  document.getElementById("btn-pay").disabled = total === 0;
  document.getElementById("btn-clear").disabled = total === 0;
}

/* ================= ACTIONS ================= */
document.getElementById("btn-clear")?.addEventListener("click", () => {
  if (confirm("Huỷ đơn hiện tại?")) {
    cart = {};
    renderCart();
  }
});

document.getElementById("btn-new-order")?.addEventListener("click", async () => {
  if (!confirm("Tạo đơn mới? Giỏ hàng hiện tại sẽ bị xoá")) return;

  const token = localStorage.getItem("token");

  await fetch("/api/orders/draft", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: "Bearer " + token
    },
    body: JSON.stringify({
      items: Object.values(cart).map(i => ({
        product_id: i.id,
        quantity: i.qty,
        price: i.price
      }))
    })
  });

  cart = {};
  renderCart();
  alert("🆕 Đã tạo đơn nháp mới");
});

document.getElementById("btn-pay")?.addEventListener("click", async () => {
  if (!confirm("Xác nhận thanh toán?")) return;

  const items = Object.values(cart).map(i => ({
    product_id: i.id,
    quantity: i.qty,
    price: i.price
  }));

  if (items.length === 0) return alert("Giỏ hàng trống");

  const res = await fetch("/api/orders/confirmed", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: "Bearer " + localStorage.getItem("token")
    },
    body: JSON.stringify({ items })
  });

  const data = await res.json();

  alert(`✅ Thanh toán thành công\nTổng tiền: ${data.total.toLocaleString()} VNĐ`);
  cart = {};
  renderCart();
});

/* ================= INIT ================= */
document.addEventListener("DOMContentLoaded", () => {
  // ❌ MẶC ĐỊNH: GIỎ LUÔN TRỐNG
  cart = {};
  localStorage.removeItem("current_cart");
  localStorage.removeItem("current_order_id");

  loadProducts();
  renderCart();
});
