from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import sqlalchemy as db
from sqlalchemy.orm import sessionmaker

from database.db import Base
from database.model import User
from middleware.file_middleware import FileMiddleware
from mcp_servers import local_file_server


class FileOwnershipTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tempdir = TemporaryDirectory()
        self.base_dir = Path(self.tempdir.name)
        self.engine = db.create_engine("sqlite:///:memory:")
        self.SessionLocal = sessionmaker(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

        db_session = self.SessionLocal()
        try:
            db_session.add_all(
                [
                    User(user_id=1, github_login="alice", email="alice@example.com", role="user"),
                    User(user_id=2, github_login="bob", email="bob@example.com", role="user"),
                ]
            )
            db_session.commit()
        finally:
            db_session.close()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _identity(self, user_id: int, login: str) -> dict[str, str | int | None]:
        return {
            "user_id": user_id,
            "github_login": login,
            "email": f"{login}@example.com",
            "role": "user",
        }

    def _patch_file_server(self, identity: dict[str, str | int | None]):
        return patch.multiple(
            local_file_server,
            BASE_DIR=self.base_dir,
            SessionLocal=self.SessionLocal,
            file_security=FileMiddleware(workspace_root=self.base_dir),
            get_current_local_user_identity=lambda: identity,
        )

    async def test_other_user_cannot_read_or_list_owned_file(self) -> None:
        with self._patch_file_server(self._identity(1, "alice")):
            created = await local_file_server.create_file("alice.txt", "alice secret")
        self.assertIn("created successfully", created)

        with self._patch_file_server(self._identity(2, "bob")):
            listed = await local_file_server.list_files()
            read_attempt = await local_file_server.read_file("alice.txt")

        self.assertEqual("No files found.", listed)
        self.assertIn("does not exist", read_attempt)

        with self._patch_file_server(self._identity(1, "alice")):
            owner_read = await local_file_server.read_file("alice.txt")
        self.assertEqual("alice secret", owner_read)

    async def test_users_can_store_same_filename_without_collision(self) -> None:
        with self._patch_file_server(self._identity(1, "alice")):
            alice_create = await local_file_server.create_file("shared.txt", "alice version")
        with self._patch_file_server(self._identity(2, "bob")):
            bob_create = await local_file_server.create_file("shared.txt", "bob version")
            bob_read = await local_file_server.read_file("shared.txt")
        with self._patch_file_server(self._identity(1, "alice")):
            alice_read = await local_file_server.read_file("shared.txt")

        self.assertIn("created successfully", alice_create)
        self.assertIn("created successfully", bob_create)
        self.assertEqual("alice version", alice_read)
        self.assertEqual("bob version", bob_read)

    async def test_list_user_files_denies_cross_user_access(self) -> None:
        with self._patch_file_server(self._identity(1, "alice")):
            created = await local_file_server.create_file("alice.txt", "alice secret")
            own_list = await local_file_server.list_user_files("alice")
            cross_user_list = await local_file_server.list_user_files("bob")

        self.assertIn("created successfully", created)
        self.assertIn("alice.txt", own_list)
        self.assertEqual("You can only view your own files.", cross_user_list)


if __name__ == "__main__":
    unittest.main()
