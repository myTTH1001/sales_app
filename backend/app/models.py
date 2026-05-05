from sqlalchemy import (Column, Integer, String, Float, 
                        ForeignKey, UniqueConstraint, CheckConstraint, Index,
                        DateTime, Enum, Table, Boolean, Numeric)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from .database import Base
import enum


# =========================================================
# 🔥 BASE MIXIN
# =========================================================
class TimestampMixin:
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

# =========================================================
# STORE
# =========================================================
class Store(Base):
    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    address = Column(String)
    users = relationship("User", back_populates="store")
    products = relationship("Product", back_populates="store")
    orders = relationship("Order", back_populates="store")
    invoices = relationship("Invoice", back_populates="store")
    stocks = relationship("Stock", back_populates="store")
    stock_movements = relationship("StockMovement",back_populates="store")
    def __repr__(self):
        return f"<Store name={self.name}>"

# =========================================================
# ROLE - PERMISSION (RBAC)
# =========================================================

# bảng trung gian
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)
)

class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)

    permissions = relationship(
        "Permission",
        secondary=role_permissions,
        back_populates="roles"
    )

    # users = relationship("User", back_populates="role")
    user_roles = relationship("UserRole", back_populates="role")
    def __repr__(self):
        return f"<Role name={self.name}>"

class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)

    roles = relationship(
        "Role",
        secondary=role_permissions,
        back_populates="permissions"
    )

    def __repr__(self):
        return f"<Permission name={self.name}>"

# 👉 Role theo từng store
class UserRole(Base):
    __tablename__ = "user_roles"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="CASCADE"), index=True, nullable=False)

    user = relationship("User", back_populates="roles")
    role = relationship("Role", back_populates="user_roles")
    store = relationship("Store")
    __table_args__ = (
    UniqueConstraint("user_id", "role_id", "store_id", name="uq_user_role_store"),
)
# =========================================================
# USER
# =========================================================
class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True,nullable=False)
    roles = relationship("UserRole", back_populates="user", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="user")
    store = relationship("Store", back_populates="users")

    def __repr__(self):
        return f"<User username={self.username}>"

# =========================================================
# PRODUCT
# =========================================================
class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    price = Column(Numeric(12, 2), nullable=False)
    image = Column(String, nullable=True)
    stock = relationship("Stock", back_populates="product", uselist=False)

    # 🔥 Multi-store
    store_id = Column(Integer, ForeignKey("stores.id"), index=True, nullable=False)
    unit = Column(String)
    store = relationship("Store", back_populates="products")
    order_items = relationship("OrderItem", back_populates="product")
    stock_movements = relationship("StockMovement", back_populates="product", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint("name", "store_id", name="uq_product_store"),
        CheckConstraint("price >= 0", name="ck_product_price_positive"),
    )
    def __repr__(self):
        return f"<Product name={self.name} price={self.price}>"

# =========================================================
# ORDER STATUS
# =========================================================
class OrderStatus(str, enum.Enum):
    draft = "draft"
    confirmed = "confirmed"
    paid = "paid"
    cancelled = "cancelled"
    deleted = "deleted"

# =========================================================
# ORDER
# =========================================================
class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # 🔥 Multi-store
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True)
    total = Column(Numeric(12, 2), default=0)
    status = Column(Enum(OrderStatus, name="order_status_enum"), default=OrderStatus.draft, nullable=False)
    view_cqt = Column(Boolean, default=False, nullable=False)
    user = relationship("User", back_populates="orders")
    store = relationship("Store", back_populates="orders")
    items = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan"
    )
    invoice = relationship(
        "Invoice",
        back_populates="order",
        uselist=False,
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_order_store_created", "store_id", "created_at"),
        Index("idx_order_user", "user_id"),
        Index("idx_order_status", "status"),
    )
    def __repr__(self):
        return f"<Order id={self.id} total={self.total}>"

# =========================================================
# ORDER ITEM
# =========================================================
class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Numeric(12, 2), nullable=False)
    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_quantity_positive"),
        CheckConstraint("price >= 0", name="ck_price_positive"),
        UniqueConstraint("order_id", "product_id", name="uq_order_product")
    )
    def __repr__(self):
        return f"<OrderItem order_id={self.order_id} product_id={self.product_id}>"

# =========================================================
# INVOICE
# =========================================================
class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(
        Integer,
        ForeignKey("orders.id", ondelete="CASCADE"),
        unique=True
    )
    # 🔥 Multi-store
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    total = Column(Numeric(12, 2), nullable=False)
    payment_method = Column(String(20), nullable=False)
    cashier_id     = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    paid_at        = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, default="paid")
    order = relationship("Order", back_populates="invoice")
    store = relationship("Store", back_populates="invoices")

    __table_args__ = (
        Index("idx_invoice_store", "store_id"),
)
    def __repr__(self):
        return f"<Invoice order_id={self.order_id} total={self.total}>"


class Stock(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), index=True)
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    quantity = Column(Integer, nullable=False, default=0)

    product = relationship("Product", back_populates="stock")
    store   = relationship("Store",   back_populates="stocks")
    __table_args__ = (
        UniqueConstraint("product_id", "store_id", name="uq_stock_product_store"),
    )

class StockMovementType(str, enum.Enum):
    IMPORT   = "IMPORT"     # nhập hàng từ NCC
    SALE     = "SALE"       # bán hàng (tự động)
    RETURN   = "RETURN"     # khách trả hàng
    ADJUST   = "ADJUST"     # chỉnh kho (kiểm kê)
    TRANSFER = "TRANSFER"   # ✅ chuyển kho giữa các cửa hàng (nếu có nhiều cửa hàng)

class StockMovement(Base, TimestampMixin):
    __tablename__ = "stock_movements"

    id           = Column(Integer, primary_key=True)
    product_id   = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False)
    store_id     = Column(Integer, ForeignKey("stores.id",   ondelete="CASCADE"), index=True, nullable=False)
    order_item_id = Column(Integer, ForeignKey("order_items.id"), nullable=True)
    quantity = Column(Integer, nullable=False)   # + nhập / - xuất
    type     = Column(Enum(StockMovementType, name="stock_movement_type_enum"), nullable=False)
    note     = Column(String, nullable=True)
    status   = Column(String, default="done")

    # ✅ TRANSFER: 2 bản ghi cùng transfer_ref — 1 âm (nguồn) + 1 dương (đích)
    transfer_ref = Column(String, nullable=True, index=True)

    order_item = relationship("OrderItem")
    product    = relationship("Product", back_populates="stock_movements")
    store      = relationship("Store",   back_populates="stock_movements")
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    user       = relationship("User")

    __table_args__ = (
        CheckConstraint("quantity != 0", name="ck_quantity_not_zero"),
        Index("idx_stock_product_store_created", "product_id", "store_id", "created_at"),
        Index("idx_stock_created_at", "created_at"),
        Index("idx_stock_transfer_ref", "transfer_ref"),    # ✅ tìm cặp transfer nhanh

        # ✅ Cập nhật constraint — TRANSFER cho phép cả + lẫn -
        CheckConstraint(
            "(type = 'IMPORT'   AND quantity > 0) OR "
            "(type = 'SALE'     AND quantity < 0) OR "
            "(type = 'RETURN'   AND quantity > 0) OR "
            "(type = 'ADJUST'                   ) OR "   # adjust: + hoặc - đều được
            "(type = 'TRANSFER'                 )",      # transfer: + hoặc - đều được
            name="ck_stock_type_quantity"
        ),
    )

    def __repr__(self):
        return f"<StockMovement product={self.product_id} qty={self.quantity} type={self.type}>"

# =========================================================
# 🔥 AUDIT LOG
# =========================================================
class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    action = Column(String)
    table_name = Column(String)
    record_id = Column(Integer)
    before = Column(JSONB)
    after = Column(JSONB)
    
    user = relationship("User")

    __table_args__ = (
    Index("idx_audit_table_record", "table_name", "record_id"),
)
    
# =========================================================
# 🔥 TOKEN BLACKLIST
# =========================================================
class TokenBlacklist(Base):
    __tablename__ = "token_blacklist"
    
    jti = Column(String, primary_key=True)
    exp = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now())