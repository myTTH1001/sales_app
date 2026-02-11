from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base
import enum

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    role = Column(String, default="user")

    orders = relationship("Order", back_populates="user")

    def __repr__(self):
        return f"<User username={self.username} role={self.role}>"
    

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    stock = Column(Integer, default=0)
    image = Column(String, nullable=True)

    order_items = relationship(
        "OrderItem",
        back_populates="product"
    )

    def __repr__(self):
        return f"<Product name={self.name} price={self.price} stock={self.stock}>"

class OrderStatus(str, enum.Enum):
    draft = "draft"
    confirmed = "confirmed"
    cancelled = "cancelled"
    deleted = "deleted"


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    total = Column(Float, default=0)
    status = Column(
        Enum(OrderStatus),
        default=OrderStatus.draft,
        nullable=False
    )

    user = relationship("User", back_populates="orders")
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

    def __repr__(self):
        return f"<Order id={self.id} total={self.total}>"


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"))
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)

    order = relationship("Order",back_populates="items")

    product = relationship("Product", back_populates="order_items")

    def __repr__(self):
        return f"<OrderItem order_id={self.order_id} product_id={self.product_id} qty={self.quantity}>"


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), unique=True)
    total = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    order = relationship("Order", back_populates="invoice")

    def __repr__(self):
        return f"<Invoice order_id={self.order_id} total={self.total}>"
