/* ================= POS STATE ================= */
let products = [];
let cart = {};
let lastInvoice = null;
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
  try {
    const res = await fetch("/api/orders/confirmed", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + localStorage.getItem("token")
      },
      body: JSON.stringify({ items })
    });

    const data = await res.json();
    if (!res.ok) {
        throw new Error(data.detail || "Thanh toán thất bại");
      }

      lastInvoice = data;
      localStorage.setItem("last_invoice", JSON.stringify(data));

      const printBtn = document.getElementById("btn-print-last");
      if (printBtn) {
        printBtn.disabled = false;
      }
    alert(`✅ Thanh toán thành công\nTổng tiền: ${data.total.toLocaleString()} VNĐ`);
    printInvoice(data);
    cart = {};
    renderCart();
  }
  catch (err) {
    console.error(err);
    alert("❌ " + err.message);
  }
});

/* ================= SEARCH PRODUCTS ================= */
/* ================= INIT ================= */
document.addEventListener("DOMContentLoaded", () => {
  // ❌ MẶC ĐỊNH: GIỎ LUÔN TRỐNG
  cart = {};
  localStorage.removeItem("current_cart");
  localStorage.removeItem("current_order_id");

  loadProducts();
  renderCart();
  // tìm kiếm sản phẩm
  const searchInput = document.getElementById("search-input");

  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      const keyword = e.target.value.trim().toLowerCase();

      if (keyword === "") {
        renderProducts(products);
        return;
      }

      const filtered = products.filter(product =>
        product.name &&
        product.name.toLowerCase().includes(keyword)
      );

      renderProducts(filtered);
    });
  }
});

async function printInvoice(invoice) {
  const cartItems = invoice.items || [];
  const total = invoice.total || 0;

  const receiptHtml = `
    <div id="receipt" style="
      width: 180px;
      padding: 10px;
      font-family: Arial, sans-serif;
      font-size: 11px;
      background: white;
      color: black;
      line-height: 1.4;
    ">
      <div style="text-align:center; margin-bottom:8px;">
        <h3 style="margin:0; font-size:14px;">ĐẶC SẢN THÀNH PHÁT</h3>
        <div style="font-size:6px; line-height:1;">
          ĐC: 11 Ngô Văn Sở, P. Trần Phú, TP. Quy Nhơn (cũ)
        </div>
        <div style="font-size:6px; line-height:1;">
          Hotline: 0936.096.350 - 093.47.47.485
        </div>
        
        <hr style="
          border: none;
          border-top: 1px dashed #000;
          width: 70%;
          margin: 4px auto;
        ">
        <div>HÓA ĐƠN BÁN HÀNG</div>
      </div>

      <div style="margin-bottom:6px;">
        <div>Mã đơn: #${invoice.order_id || "---"}</div>
        <div>Ngày: ${new Date().toLocaleString("vi-VN")}</div>
        <div>Thu ngân: ${invoice.cashier || localStorage.getItem("username") || "Nhân viên"}</div>
      </div>

      <hr style="border:none;border-top:1px dashed #000;">

      ${cartItems.map(item => `
        <div style="margin-bottom:6px;">
          <div style="font-weight:bold;">${item.name || item.product_name}</div>
          <div style="display:flex;justify-content:space-between;">
            <span>${item.quantity || item.qty} x ${Number(item.price).toLocaleString()}đ</span>
            <span>${((item.quantity || item.qty) * item.price).toLocaleString()}đ</span>
          </div>
        </div>
      `).join("")}

      <hr style="border:none;border-top:1px dashed #000;">

      <div style="display:flex;justify-content:space-between;font-weight:bold;font-size:13px;">
        <span>Tổng cộng</span>
        <span>${Number(total).toLocaleString()}đ</span>
      </div>

      <div style="text-align:center;margin-top:10px;font-size:11px;">
        Cảm ơn quý khách!
        <img 
          src="/static/images/QR.jpg" 
          alt="QR thanh toán"
          style="
            width: 90px;
            height: 90px;
            object-fit: contain;
            display: block;
            margin: 0 auto;
          "
        >
      </div>
    </div>
  `;

  const tempDiv = document.createElement("div");
  tempDiv.style.position = "fixed";
  tempDiv.style.left = "-99999px";
  tempDiv.style.top = "0";
  tempDiv.innerHTML = receiptHtml;
  document.body.appendChild(tempDiv);

  const receiptElement = tempDiv.querySelector("#receipt");

  const canvas = await html2canvas(receiptElement, {
    scale: 3,
    backgroundColor: "#ffffff"
  });

  // Resize về đúng khổ in 384px (48mm)
  const targetWidth = 384; 
  const scaleFactor = targetWidth / canvas.width;
  const targetHeight = canvas.height * scaleFactor;

  const resizedCanvas = document.createElement("canvas");
  resizedCanvas.width = targetWidth;
  resizedCanvas.height = targetHeight;

  const ctx = resizedCanvas.getContext("2d");
  ctx.drawImage(canvas, 0, 0, targetWidth, targetHeight);

  const imageData = resizedCanvas.toDataURL("image/png");
  // const imageData = canvas.toDataURL("image/png");

  // Sau khi có imageData
  fetch("/api/orders/print", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ imageData })
  })
  .then(res => res.json())
  .then(data => {
    alert(data.message || "In hóa đơn thành công!");
  })
  .catch(err => {
    console.error("Lỗi in hóa đơn:", err);
    alert("Không thể in hóa đơn");
  });
  document.body.removeChild(tempDiv);

  const previewWindow = window.open("", "_blank");

  previewWindow.document.write(`
    <html>
      <head>
        <title>Hóa đơn #${invoice.order_id}</title>
        <style>
          body {
            font-family: Arial, sans-serif;
            background: #f3f4f6;
            margin: 0;
            padding: 20px;
            text-align: center;
          }

          .receipt-container {
            max-width: 400px;
            margin: auto;
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
          }

          .receipt-container img {
            width: 100%;
            border: 1px solid #ddd;
            border-radius: 8px;
          }

          .download-btn {
            display: inline-block;
            margin-top: 20px;
            padding: 12px 18px;
            background: #2563eb;
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-weight: bold;
          }
        </style>
      </head>
      <body>
        <div class="receipt-container">
          <h2>Hóa đơn #${invoice.order_id}</h2>
          <img src="${imageData}" alt="Hóa đơn">
          <br>
          <a class="download-btn" href="${imageData}" download="hoa-don-${invoice.order_id}.png">
            Tải hóa đơn xuống
          </a>
        </div>
      </body>
    </html>
  `);

  previewWindow.document.close();
}

document.getElementById("btn-print-last")?.addEventListener("click", () => {
  const invoice = lastInvoice || JSON.parse(localStorage.getItem("last_invoice"));

  if (!invoice) {
    return alert("Không có hóa đơn để xem lại");
  }

  printInvoice(invoice);
});
