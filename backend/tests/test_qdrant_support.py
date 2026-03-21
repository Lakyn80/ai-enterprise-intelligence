from unittest.mock import patch

from app.vector.qdrant_support import create_async_qdrant_client


def test_create_async_qdrant_client_disables_version_check():
    with patch("qdrant_client.AsyncQdrantClient") as mock_client:
        create_async_qdrant_client()

    assert mock_client.call_args.kwargs["check_compatibility"] is False
