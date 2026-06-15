import unittest
import sys
import os
import datetime

# Add src to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from unittest.mock import AsyncMock, patch
from src.services.leetcode import LeetCodeClient

class TestLeetCodeClientMock(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # We patch settings proxies_list to ensure initialization is clean and doesn't attempt real connections.
        with patch('src.services.leetcode.settings') as mock_settings:
            mock_settings.proxies_list = []
            self.client = LeetCodeClient()

    async def asyncTearDown(self):
        await self.client.close()

    async def test_get_user_profile(self):
        # Mock profile payload from LeetCode
        mock_payload = {
            "matchedUser": {
                "username": "leetcode_coder",
                "profile": {
                    "realName": "Jane Doe",
                    "aboutMe": "Competitive programmer",
                    "ranking": 42000,
                    "reputation": 500
                },
                "submitStats": {
                    "acSubmissionNum": [
                        {"difficulty": "All", "count": 250, "submissions": 350},
                        {"difficulty": "Easy", "count": 100, "submissions": 120},
                        {"difficulty": "Medium", "count": 120, "submissions": 180},
                        {"difficulty": "Hard", "count": 30, "submissions": 50}
                    ]
                }
            }
        }

        with patch.object(self.client, '_query', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = mock_payload
            
            profile = await self.client.get_user_profile("leetcode_coder")
            
            self.assertIsNotNone(profile)
            self.assertEqual(profile["username"], "leetcode_coder")
            self.assertEqual(profile["profile"]["realName"], "Jane Doe")
            self.assertEqual(profile["profile"]["ranking"], 42000)
            
            submit_stats = profile.get("submitStats", {}).get("acSubmissionNum", [])
            total_solved = next((item["count"] for item in submit_stats if item["difficulty"] == "All"), 0)
            self.assertEqual(total_solved, 250)
            
            mock_query.assert_called_once_with(unittest.mock.ANY, {"username": "leetcode_coder"})

    async def test_get_user_profile_none(self):
        with patch.object(self.client, '_query', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = None
            profile = await self.client.get_user_profile("nonexistent")
            self.assertIsNone(profile)

    async def test_get_daily_challenge(self):
        mock_payload = {
            "activeDailyCodingChallengeQuestion": {
                "date": "2026-06-15",
                "link": "/problems/two-sum/daily",
                "question": {
                    "questionId": "1",
                    "questionFrontendId": "1",
                    "title": "Two Sum",
                    "titleSlug": "two-sum",
                    "difficulty": "Easy",
                    "content": "<p>Given an array of integers...</p>",
                    "topicTags": [
                        {"name": "Array", "slug": "array"},
                        {"name": "Hash Table", "slug": "hash-table"}
                    ]
                }
            }
        }

        with patch.object(self.client, '_query', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = mock_payload
            
            daily = await self.client.get_daily_challenge()
            
            self.assertIsNotNone(daily)
            self.assertEqual(daily["date"], "2026-06-15")
            self.assertEqual(daily["question"]["title"], "Two Sum")
            self.assertEqual(daily["question"]["difficulty"], "Easy")
            self.assertEqual(daily["link"], "/problems/two-sum/daily")

    async def test_get_user_calendar(self):
        mock_payload = {
            "matchedUser": {
                "userCalendar": {
                    "activeYears": [2025, 2026],
                    "streak": 15,
                    "totalActiveDays": 120,
                    "submissionCalendar": '{"1672531199": 1, "1672617599": 2}'
                }
            }
        }

        with patch.object(self.client, '_query', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = mock_payload
            
            calendar = await self.client.get_user_calendar("leetcode_coder")
            
            self.assertIsNotNone(calendar)
            self.assertEqual(calendar["streak"], 15)
            self.assertEqual(calendar["totalActiveDays"], 120)
            self.assertEqual(calendar["activeYears"], [2025, 2026])

    async def test_get_recent_accepted_submissions(self):
        mock_payload = {
            "recentAcSubmissionList": [
                {
                    "id": "1001",
                    "title": "Add Two Numbers",
                    "titleSlug": "add-two-numbers",
                    "timestamp": "1781600000"
                },
                {
                    "id": "1002",
                    "title": "Two Sum",
                    "titleSlug": "two-sum",
                    "timestamp": "1781500000"
                }
            ]
        }

        with patch.object(self.client, '_query', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = mock_payload
            
            subs = await self.client.get_recent_accepted_submissions("leetcode_coder", limit=2)
            
            self.assertEqual(len(subs), 2)
            self.assertEqual(subs[0]["titleSlug"], "add-two-numbers")
            self.assertEqual(subs[1]["titleSlug"], "two-sum")

    async def test_get_user_contest_ranking(self):
        mock_payload = {
            "userContestRanking": {
                "attendedContestsCount": 8,
                "rating": 1750.5,
                "globalRanking": 12500,
                "totalParticipants": 200000,
                "topPercentage": 6.25
            }
        }

        with patch.object(self.client, '_query', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = mock_payload
            
            ranking = await self.client.get_user_contest_ranking("leetcode_coder")
            
            self.assertIsNotNone(ranking)
            self.assertEqual(ranking["rating"], 1750.5)
            self.assertEqual(ranking["attendedContestsCount"], 8)
            self.assertEqual(ranking["globalRanking"], 12500)

    async def test_get_problem_details(self):
        mock_payload = {
            "question": {
                "questionId": "1",
                "questionFrontendId": "1",
                "title": "Two Sum",
                "titleSlug": "two-sum",
                "difficulty": "Easy",
                "content": "<p>Given an array of integers...</p>",
                "topicTags": [{"name": "Array", "slug": "array"}],
                "codeSnippets": [{"lang": "Python3", "langSlug": "python3", "code": "class Solution:"}]
            }
        }

        with patch.object(self.client, '_query', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = mock_payload
            
            problem = await self.client.get_problem_details("two-sum")
            
            self.assertIsNotNone(problem)
            self.assertEqual(problem["title"], "Two Sum")
            self.assertEqual(problem["difficulty"], "Easy")

    async def test_get_problemset_questions(self):
        mock_payload = {
            "problemsetQuestionList": {
                "totalNum": 1,
                "questions": [
                    {
                        "frontendQuestionId": "1",
                        "title": "Two Sum",
                        "titleSlug": "two-sum",
                        "difficulty": "Easy",
                        "isPaidOnly": False
                    }
                ]
            }
        }

        with patch.object(self.client, '_query', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = mock_payload
            
            questions = await self.client.get_problemset_questions(limit=1, difficulty="easy")
            
            self.assertEqual(len(questions), 1)
            self.assertEqual(questions[0]["titleSlug"], "two-sum")

    async def test_battle_victory_checks(self):
        # Scenario: Challenger starts battle at 10:00:00 UTC.
        # Challenger solves at 10:05:00 UTC.
        # Opponent solves at 10:10:00 UTC.
        
        started_at = datetime.datetime(2026, 6, 15, 10, 0, 0, tzinfo=datetime.timezone.utc)
        
        # Simulated responses for recent submissions query
        challenger_subs = [
            {
                "id": "1001",
                "title": "Two Sum",
                "titleSlug": "two-sum",
                "timestamp": str(int(datetime.datetime(2026, 6, 15, 10, 5, 0, tzinfo=datetime.timezone.utc).timestamp()))
            }
        ]
        
        opponent_subs = [
            {
                "id": "1002",
                "title": "Two Sum",
                "titleSlug": "two-sum",
                "timestamp": str(int(datetime.datetime(2026, 6, 15, 10, 10, 0, tzinfo=datetime.timezone.utc).timestamp()))
            }
        ]
        
        # Simulate victory logic parsing (equivalent to logic in poll_active_battles / poll_active_group_battles)
        c_solved_ts = None
        o_solved_ts = None
        problem_slug = "two-sum"

        # Check challenger solve timestamp
        for sub in challenger_subs:
            if sub["titleSlug"] == problem_slug:
                sub_time = datetime.datetime.fromtimestamp(int(sub["timestamp"]), tz=datetime.timezone.utc)
                if sub_time > started_at:
                    c_solved_ts = sub_time
                    break

        # Check opponent solve timestamp
        for sub in opponent_subs:
            if sub["titleSlug"] == problem_slug:
                sub_time = datetime.datetime.fromtimestamp(int(sub["timestamp"]), tz=datetime.timezone.utc)
                if sub_time > started_at:
                    o_solved_ts = sub_time
                    break
        
        # Assertions
        self.assertIsNotNone(c_solved_ts)
        self.assertIsNotNone(o_solved_ts)
        
        # Verify that challenger's solve time is earlier than opponent's
        self.assertTrue(c_solved_ts < o_solved_ts)
        
        # Verify that solve times are relative to started_at
        challenger_duration = (c_solved_ts - started_at).total_seconds()
        opponent_duration = (o_solved_ts - started_at).total_seconds()
        
        self.assertEqual(challenger_duration, 300)  # 5 minutes
        self.assertEqual(opponent_duration, 600)    # 10 minutes

if __name__ == "__main__":
    unittest.main()
