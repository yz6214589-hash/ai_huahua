"""
Repository基类单元测试
"""
import pytest
from unittest.mock import patch, MagicMock
from core.repository.base import BaseRepository


class TestBaseRepository:
    def setup_method(self):
        self.repo = BaseRepository()

    @patch("core.repository.base.executemany")
    @patch("core.repository.base.execute")
    @patch("core.repository.base.query_dict")
    @patch("core.repository.base.load_mysql_config")
    @patch("core.repository.base.connect")
    def test_query_returns_list(self, mock_connect, mock_config, mock_qd, mock_exec, mock_em):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_qd.return_value = [{"id": "1", "name": "test"}]
        result = self.repo._query("SELECT * FROM test")
        assert result == [{"id": "1", "name": "test"}]
        mock_conn.close.assert_called_once()

    @patch("core.repository.base.query_dict")
    @patch("core.repository.base.load_mysql_config")
    @patch("core.repository.base.connect")
    def test_query_one_returns_dict(self, mock_connect, mock_config, mock_qd):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_qd.return_value = [{"id": "1"}]
        result = self.repo._query_one("SELECT * FROM test")
        assert result == {"id": "1"}

    @patch("core.repository.base.query_dict")
    @patch("core.repository.base.load_mysql_config")
    @patch("core.repository.base.connect")
    def test_query_one_returns_none(self, mock_connect, mock_config, mock_qd):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_qd.return_value = []
        result = self.repo._query_one("SELECT * FROM test")
        assert result is None

    @patch("core.repository.base.execute")
    @patch("core.repository.base.load_mysql_config")
    @patch("core.repository.base.connect")
    def test_execute_returns_affected(self, mock_connect, mock_config, mock_exec):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_exec.return_value = 1
        result = self.repo._execute("INSERT INTO test VALUES (%s)", ("val",))
        assert result == 1
        mock_conn.close.assert_called_once()
