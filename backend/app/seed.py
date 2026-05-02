# app/seed.py

from app.database import SessionLocal
from app import models
from app.security import hash_password
from app.permissions import all_permissions, permissions_for_role, ROLE_TEMPLATES


def seed():
    db = SessionLocal()
    try:
        # ① Store
        store = db.query(models.Store).filter_by(name="Cửa hàng chính").first()
        if not store:
            store = models.Store(name="Cửa hàng chính", address="11 Ngô Văn Sở")
            db.add(store)
            db.flush()

        # ② Sync toàn bộ permissions từ registry vào DB
        # — permission có trong code nhưng chưa có trong DB → tạo mới
        # — không xóa permission cũ (tránh mất data production)
        perm_map = {}
        for perm_name in all_permissions():
            p = db.query(models.Permission).filter_by(name=perm_name).first()
            if not p:
                p = models.Permission(name=perm_name)
                db.add(p)
                db.flush()
                print(f"  [+] Permission mới: {perm_name}")
            perm_map[perm_name] = p

        # ③ Sync roles và gán permissions từ template
        for role_name in ROLE_TEMPLATES:
            role = db.query(models.Role).filter_by(name=role_name).first()
            if not role:
                role = models.Role(name=role_name)
                db.add(role)
                db.flush()
                print(f"  [+] Role mới: {role_name}")

            # Cập nhật permissions theo template (idempotent)
            role.permissions = [
                perm_map[n]
                for n in permissions_for_role(role_name)
                if n in perm_map
            ]

        # ④ User admin
        owner_role = db.query(models.Role).filter_by(name="owner").first()
        admin = db.query(models.User).filter_by(username="admin").first()
        if not admin:
            admin = models.User(
                username="admin",
                password=hash_password("admin123"),
                store_id=store.id,
                is_active=True
            )
            db.add(admin)
            db.flush()

        existing = db.query(models.UserRole).filter_by(
            user_id=admin.id, role_id=owner_role.id, store_id=store.id
        ).first()
        if not existing:
            db.add(models.UserRole(
                user_id=admin.id, role_id=owner_role.id, store_id=store.id
            ))

        db.commit()
        print("✅ Seed hoàn tất")

    except Exception as e:
        db.rollback()
        print(f"❌ Lỗi: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()