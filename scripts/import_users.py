"""批量创建/更新用户账号。

用法:
    python scripts/import_users.py <文件.csv>

CSV 格式 (无表头):
    username,email,password,role
    # role 可选: admin, professional, normal
    # 以 # 开头的行会被忽略

注意: 请先执行 python scripts/init_db.py 初始化数据库表。
"""

import csv
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "UI", "backend")))

from app.core.database import SessionLocal
from app.models.user import User
from app.auth.service import get_password_hash

VALID_ROLES = {"admin", "professional", "normal"}


def upsert_user(db, username: str, email: str, password: str, role: str):
    role = role.strip().lower()
    if role not in VALID_ROLES:
        print(f"  跳过: 无效角色 '{role}'")
        return

    existing = db.query(User).filter(User.username == username).first()
    if existing:
        existing.role = role
        existing.email = email
        existing.hashed_password = get_password_hash(password)
        db.commit()
        print(f"  更新: {username} -> 角色={role}, 密码已重置")
    else:
        user = User(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            role=role,
        )
        db.add(user)
        db.commit()
        print(f"  创建: {username} / {password}  角色={role}")


def main():
    if len(sys.argv) < 2:
        print("用法: python scripts/import_users.py <文件.csv>", file=sys.stderr)
        sys.exit(1)

    csv_path = sys.argv[1]
    if not os.path.isfile(csv_path):
        print(f"错误: 文件不存在 '{csv_path}'", file=sys.stderr)
        sys.exit(1)

    db = SessionLocal()
    try:
        created = 0
        updated = 0
        skipped = 0
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                line = ",".join(row).strip()
                if not line or line.startswith("#"):
                    continue

                if len(row) < 4:
                    print(f"  跳过: 列数不足 (需要4列): {line[:60]}")
                    skipped += 1
                    continue

                username, email, password, role = row[0].strip(), row[1].strip(), row[2].strip(), row[3].strip()
                if not username or not email or not password:
                    print(f"  跳过: 必填字段为空: {line[:60]}")
                    skipped += 1
                    continue

                before = db.query(User).filter(User.username == username).first() is not None
                upsert_user(db, username, email, password, role)
                if before:
                    updated += 1
                else:
                    created += 1

        print(f"\n完成: 新建 {created}, 更新 {updated}, 跳过 {skipped}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
