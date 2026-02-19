# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""Search tests"""

from openviking.message import TextPart
from openviking_cli.retrieve.types import ContextType, QueryPlan, TypedQuery


class TestFind:
    """Test find quick search"""

    async def test_find(self, client_with_resource_sync):
        """Test basic search"""
        client, uri = client_with_resource_sync

        result = await client.find(query="sample document")

        assert hasattr(result, "resources")
        assert hasattr(result, "memories")
        assert hasattr(result, "skills")
        assert hasattr(result, "total")

        """Test limiting result count"""
        result = await client.find(query="test", limit=5)

        assert len(result.resources) <= 5

        """Test search with target URI"""
        result = await client.find(query="sample", target_uri=uri)

        assert hasattr(result, "resources")

        """Test score threshold filtering"""
        result = await client.find(query="sample document", score_threshold=0.1)

        # Verify all results have score >= threshold
        for res in result.resources:
            assert res.score >= 0.1

        """Test no matching results"""
        result = await client.find(query="completely_random_nonexistent_query_xyz123")

        assert result.total >= 0


class TestSearch:
    """Test search complex search"""

    async def test_search(self, client_with_resource_sync):
        """Test basic complex search"""
        client, uri = client_with_resource_sync

        result = await client.search(query="sample document")

        assert hasattr(result, "resources")

        """Test search with session context"""
        session = client.session()
        # Add some messages to establish context
        session.add_message("user", [TextPart("I need help with testing")])

        result = await client.search(query="testing help", session=session)

        assert hasattr(result, "resources")

        """Test limiting result count"""
        result = await client.search(query="sample", limit=3)

        assert len(result.resources) <= 3

        """Test complex search with target URI"""
        parent_uri = "/".join(uri.split("/")[:-1]) + "/"

        result = await client.search(query="sample", target_uri=parent_uri)

        assert hasattr(result, "resources")

    async def test_search_fallbacks_to_legacy_summaries(
        self, client_with_resource_sync, monkeypatch
    ):
        """Regression: `search` should consume legacy `summaries` when `summary` is absent."""
        client, _ = client_with_resource_sync
        session = client.session()

        monkeypatch.setattr(
            session,
            "get_context_for_search",
            lambda _query: {
                "summaries": ["archive summary one", "archive summary two"],
                "recent_messages": [],
            },
        )

        captured = {"compression_summary": ""}

        async def fake_analyze(
            _self,
            compression_summary,
            messages,
            current_message=None,
            context_type=None,
            target_abstract="",
        ):
            captured["compression_summary"] = compression_summary
            return QueryPlan(
                queries=[
                    TypedQuery(
                        query=current_message or "sample",
                        context_type=ContextType.RESOURCE,
                        intent="test",
                        priority=1,
                    )
                ],
                session_context="test",
                reasoning="test",
            )

        monkeypatch.setattr(
            "openviking.retrieve.intent_analyzer.IntentAnalyzer.analyze",
            fake_analyze,
        )

        await client.search(query="sample", session=session, limit=3)

        assert captured["compression_summary"]
        assert "archive summary one" in captured["compression_summary"]
        assert "archive summary two" in captured["compression_summary"]
