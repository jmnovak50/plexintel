from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import patch

from fastapi.encoders import jsonable_encoder

from api.routes import agent_tools
from api.services.agent_tool_service import (
    AgentRecommendation,
    AgentRecommendationsResponse,
    AgentUser,
    AgentUsersResponse,
    LibraryItem,
    LibrarySearchResponse,
    RecentLibraryAdditionsResponse,
    RecentLibraryItem,
    WatchHistoryItem,
    WatchHistoryResponse,
)


class AgentToolsRouteTests(unittest.TestCase):
    def test_recommendations_route_uses_shared_service_shape(self):
        payload = AgentRecommendationsResponse(
            user="jmnovak",
            count=1,
            items=[
                AgentRecommendation(
                    rating_key=5,
                    title="Arrival",
                    media_type="movie",
                    score=0.88,
                )
            ],
        )

        with patch.object(agent_tools, "get_agent_recommendations", return_value=payload):
            response = agent_tools.agent_get_recommendations(user="jmnovak")

        data = jsonable_encoder(response)
        self.assertEqual(data["user"], "jmnovak")
        self.assertEqual(data["items"][0]["title"], "Arrival")
        self.assertEqual(data["items"][0]["score"], 0.88)

    def test_search_and_item_routes_preserve_payload_shapes(self):
        search_payload = LibrarySearchResponse(
            query="blade",
            count=1,
            items=[
                LibraryItem(
                    rating_key=42,
                    title="Blade Runner 2049",
                    media_type="movie",
                    year=2017,
                )
            ],
        )
        item_payload = LibraryItem(
            rating_key=42,
            title="Blade Runner 2049",
            media_type="movie",
            summary="Replicants.",
        )

        with patch.object(agent_tools, "search_agent_library", return_value=search_payload):
            with patch.object(agent_tools, "get_agent_library_item", return_value=item_payload):
                search_response = agent_tools.agent_search_library(q="blade")
                item_response = agent_tools.agent_get_item(42)

        search_data = jsonable_encoder(search_response)
        item_data = jsonable_encoder(item_response)
        self.assertEqual(search_data["items"][0]["year"], 2017)
        self.assertEqual(item_data["summary"], "Replicants.")

    def test_recent_additions_route_preserves_payload_shape(self):
        recent_payload = RecentLibraryAdditionsResponse(
            media_type="movie",
            days=7,
            count=1,
            items=[
                RecentLibraryItem(
                    rating_key=88,
                    title="Black Bag",
                    media_type="movie",
                    year=2025,
                )
            ],
        )

        with patch.object(agent_tools, "get_recent_library_additions", return_value=recent_payload):
            response = agent_tools.agent_recent_library_additions(media_type="movie", days=7, limit=10)

        data = jsonable_encoder(response)
        self.assertEqual(data["media_type"], "movie")
        self.assertEqual(data["days"], 7)
        self.assertEqual(data["items"][0]["title"], "Black Bag")

    def test_users_and_watch_history_routes_preserve_payload_shapes(self):
        users_payload = AgentUsersResponse(
            count=1,
            items=[AgentUser(username="jmnovak", friendly_name="Jason")],
        )
        history_payload = WatchHistoryResponse(
            user="jmnovak",
            engaged_only=False,
            count=1,
            results=[
                WatchHistoryItem(
                    watch_id=1,
                    username="jmnovak",
                    friendly_name="Jason",
                    rating_key=777,
                    watched_at=datetime(2026, 3, 2, 8, 30, 0),
                    played_duration=3500,
                    media_duration=4000,
                    percent_complete=0.875,
                    engaged=True,
                    media_type="movie",
                    show_title=None,
                    title="Heat",
                    summary="Crime drama",
                    season_number=None,
                    episode_number=None,
                    rating=8.4,
                    year=1995,
                    genres="Crime",
                    actors="Al Pacino",
                    directors="Michael Mann",
                )
            ],
        )

        with patch.object(agent_tools, "list_agent_users", return_value=users_payload):
            with patch.object(agent_tools, "get_agent_watch_history", return_value=history_payload):
                users_response = agent_tools.agent_list_users()
                history_response = agent_tools.agent_watch_history()

        users_data = jsonable_encoder(users_response)
        history_data = jsonable_encoder(history_response)
        self.assertEqual(users_data["items"][0]["friendly_name"], "Jason")
        self.assertEqual(history_data["results"][0]["rating"], 8.4)


if __name__ == "__main__":
    unittest.main()
