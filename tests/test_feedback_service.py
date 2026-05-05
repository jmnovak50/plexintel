from __future__ import annotations

import unittest

from api.services.feedback_service import action_defaults


class FeedbackServiceTests(unittest.TestCase):
    def test_interested_feedback_is_not_suppressing(self):
        defaults = action_defaults("interested")

        self.assertEqual(defaults["feedback"], "interested")
        self.assertFalse(defaults["suppress"])
        self.assertEqual(defaults["reason_code"], "interested")
        self.assertEqual(defaults["plex_watchlist_status"], "unresolved")

    def test_negative_and_watched_feedback_are_suppressing(self):
        for action in ("never_watch", "watched_like", "watched_dislike"):
            with self.subTest(action=action):
                defaults = action_defaults(action)

                self.assertEqual(defaults["feedback"], action)
                self.assertTrue(defaults["suppress"])
                self.assertEqual(defaults["reason_code"], action)
                self.assertEqual(defaults["plex_watchlist_status"], "not_applicable")


if __name__ == "__main__":
    unittest.main()
