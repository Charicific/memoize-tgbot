import logging
import random
import httpx
from typing import Optional, Dict, List, Any
from src.config import settings

logger = logging.getLogger(__name__)

class LeetCodeClient:
    BASE_URL = "https://leetcode.com/graphql"
    
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1"
    ]

    def __init__(self):
        self.clients = []
        # Main direct connection client
        self.clients.append(httpx.AsyncClient(timeout=10.0))
        
        # Initialize additional clients for configured proxies
        for proxy in settings.proxies_list:
            try:
                client = httpx.AsyncClient(proxies={"all://": proxy}, timeout=10.0)
                self.clients.append(client)
                logger.info(f"Initialized proxy client for: {proxy}")
            except Exception as e:
                logger.error(f"Error initializing proxy client for {proxy}: {e}")

    async def close(self):
        for client in self.clients:
            await client.aclose()

    async def _query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        payload = {"query": query, "variables": variables or {}}
        # Pick random client from the pool
        client = random.choice(self.clients)
        
        # Pick random User-Agent
        headers = {
            "Content-Type": "application/json",
            "Referer": "https://leetcode.com",
            "User-Agent": random.choice(self.USER_AGENTS)
        }
        import time
        start_time = time.time()
        try:
            response = await client.post(self.BASE_URL, json=payload, headers=headers)
            latency = (time.time() - start_time) * 1000
            if latency > 5000:
                logger.warning(f"SLOW LeetCode API Query ({latency:.1f}ms)")

            if response.status_code == 200:
                data = response.json()
                if "errors" in data:
                    logger.error(f"LeetCode GraphQL errors: {data['errors']}")
                    return None
                return data.get("data")
            else:
                logger.error(f"LeetCode request failed with status: {response.status_code}, response: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error calling LeetCode API: {e}")
            return None

    async def get_user_profile(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Fetches user profile, solved stats, and ranking.
        """
        query = """
        query getUserProfile($username: String!) {
          matchedUser(username: $username) {
            username
            profile {
              realName
              aboutMe
              ranking
              reputation
            }
            submitStats {
              acSubmissionNum {
                difficulty
                count
                submissions
              }
            }
          }
        }
        """
        data = await self._query(query, {"username": username})
        if not data or not data.get("matchedUser"):
            return None
        return data["matchedUser"]

    async def get_user_contest_ranking(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Fetches user contest ranking details.
        """
        query = """
        query userContestRankingInfo($username: String!) {
          userContestRanking(username: $username) {
            attendedContestsCount
            rating
            globalRanking
            totalParticipants
            topPercentage
          }
        }
        """
        data = await self._query(query, {"username": username})
        if not data:
            return None
        return data.get("userContestRanking")

    async def get_recent_accepted_submissions(self, username: str, limit: int = 15) -> List[Dict[str, Any]]:
        """
        Fetches the user's recent accepted submissions.
        """
        query = """
        query getRecentSubmissions($username: String!, $limit: Int!) {
          recentAcSubmissionList(username: $username, limit: $limit) {
            id
            title
            titleSlug
            timestamp
          }
        }
        """
        data = await self._query(query, {"username": username, "limit": limit})
        if not data or not data.get("recentAcSubmissionList"):
            return []
        return data["recentAcSubmissionList"]

    async def get_daily_challenge(self) -> Optional[Dict[str, Any]]:
        """
        Fetches the active daily challenge.
        """
        query = """
        query questionOfToday {
          activeDailyCodingChallengeQuestion {
            date
            link
            question {
              questionId
              questionFrontendId
              title
              titleSlug
              difficulty
              content
              topicTags {
                name
                slug
              }
            }
          }
        }
        """
        data = await self._query(query)
        if not data or not data.get("activeDailyCodingChallengeQuestion"):
            return None
        return data["activeDailyCodingChallengeQuestion"]

    async def get_problem_details(self, title_slug: str) -> Optional[Dict[str, Any]]:
        """
        Fetches problem description, difficulties, topic tags, and code snippets.
        """
        query = """
        query questionData($titleSlug: String!) {
          question(titleSlug: $titleSlug) {
            questionId
            questionFrontendId
            title
            titleSlug
            difficulty
            content
            topicTags {
              name
              slug
            }
            codeSnippets {
              lang
              langSlug
              code
            }
          }
        }
        """
        data = await self._query(query, {"titleSlug": title_slug})
        if not data or not data.get("question"):
            return None
        return data["question"]

    async def get_problemset_questions(self, limit: int = 50, skip: int = 0, difficulty: Optional[str] = None, tag_slug: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetches a list of problems, filtered by difficulty and tag.
        """
        query = """
        query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
          problemsetQuestionList: questionList(
            categorySlug: $categorySlug
            limit: $limit
            skip: $skip
            filters: $filters
          ) {
            totalNum
            questions: data {
              frontendQuestionId: questionFrontendId
              title
              titleSlug
              difficulty
              isPaidOnly
            }
          }
        }
        """
        filters = {}
        if difficulty:
            filters["difficulty"] = difficulty.upper()
        if tag_slug:
            filters["tags"] = [tag_slug]

        data = await self._query(query, {
            "categorySlug": "",
            "limit": limit,
            "skip": skip,
            "filters": filters
        })
        if not data or not data.get("problemsetQuestionList"):
            return []
        return data["problemsetQuestionList"].get("questions", [])

    async def get_contests(self) -> List[Dict[str, Any]]:
        """
        Fetches the LeetCode contest schedule.
        """
        query = """
        query {
          allContests {
            title
            titleSlug
            startTime
            duration
          }
        }
        """
        data = await self._query(query)
        if not data or not data.get("allContests"):
            return []
        return data["allContests"]

    async def get_user_calendar(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Fetches user submission calendar and active streak details.
        """
        query = """
        query userProfileCalendar($username: String!) {
          matchedUser(username: $username) {
            userCalendar {
              activeYears
              streak
              totalActiveDays
              submissionCalendar
            }
          }
        }
        """
        data = await self._query(query, {"username": username})
        if not data or not data.get("matchedUser"):
            return None
        return data["matchedUser"].get("userCalendar")
