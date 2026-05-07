# app/permissions.py

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class PermissionGroup:
    name: str
    permissions: List[str]


# =========================================================
# ĐỊNH NGHĨA TẤT CẢ PERMISSIONS THEO MODULE
# Thêm module mới → thêm 1 block ở đây, không cần đụng gì khác
# =========================================================

PERMISSIONS: Dict[str, PermissionGroup] = {

    "admin": PermissionGroup(
        name="Quản trị hệ thống",
        permissions=[
            "manage_roles",
            "manage_users",
        ]
    ),

    "product": PermissionGroup(
        name="Sản phẩm",
        permissions=[
            "product:view",
            "product:create",
            "product:update",
            "product:delete",
        ]
    ),

    "order": PermissionGroup(
        name="Đơn hàng",
        permissions=[
            "order:view",
            "order:create",
            "order:confirm",
            "order:cancel",
        ]
    ),

    "invoice": PermissionGroup(
        name="Hóa đơn",
        permissions=[
            "invoice:view",
            "invoice:export",
            "invoice:create",
            "invoice:cancel",
        ]
    ),

    "stock": PermissionGroup(
        name="Kho",
        permissions=[
            "stock:view",       #Xem tồn kho
            "stock:import",     #Nhập kho (tăng tồn)
            "stock:adjust",     #Điều chỉnh tồn (tăng/giảm, dùng khi kiểm kho)
            "stock:sale",       #Giảm tồn khi bán hàng (nếu muốn tự động giảm khi tạo đơn, thay vì phải gọi endpoint nhập kho)
            "stock:return",     #Tăng tồn khi trả hàng (nếu muốn tự động tăng khi hủy đơn, thay vì phải gọi endpoint nhập kho)
            "stock:transfer",   #Chuyển kho giữa các cửa hàng (nếu có nhiều cửa hàng)
        ]
    ),

    "report": PermissionGroup(
        name="Báo cáo",
        permissions=[
            "report:view",
            "report:export",
        ]
    ),
}


# =========================================================
# ROLE TEMPLATES — mỗi role mặc định có những permission gì
# Thêm role mới → thêm 1 entry ở đây
# =========================================================

ROLE_TEMPLATES: Dict[str, List[str]] = {

    "owner": [p for group in PERMISSIONS.values() for p in group.permissions],

    "manager": [
        "manage_users",
        "product:view", "product:create", "product:update", "product:delete",
        "order:view", "order:create", "order:confirm", "order:cancel",
        "invoice:view", "invoice:export", "invoice:create", "invoice:cancel",
        "stock:view", "stock:import", "stock:adjust", "stock:return", "stock:transfer",
        "report:view", "report:export",
    ],

    "staff": [
        "product:view", "product:create", "product:update",
        "order:view", "order:create",
        "invoice:view",
        "stock:view", "stock:import", "stock:return",  # không có adjust, transfer
    ],

    "cashier": [
        "product:view",
        "order:view", "order:create", "order:confirm",
        "invoice:view", "invoice:create", "invoice:cancel",
        "stock:view",   # chỉ xem — không chạm tồn kho
    ],
}


# =========================================================
# HELPERS
# =========================================================

def all_permissions() -> List[str]:
    """Trả về flat list toàn bộ permissions."""
    return [p for group in PERMISSIONS.values() for p in group.permissions]


def permissions_for_role(role_name: str) -> List[str]:
    """Trả về list permissions của 1 role template."""
    return ROLE_TEMPLATES.get(role_name, [])