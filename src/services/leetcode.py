import logging
import random
import httpx
import difflib
from typing import Optional, Dict, List, Any
from groq import AsyncGroq
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

        # Initialize Groq client for fuzzy typo corrections
        self.groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)

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
        Fetches the user's recent accepted submissions and enriches them with question numbers and difficulties in parallel.
        """
        import asyncio
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
        
        submissions = data["recentAcSubmissionList"]
        
        # Parallel enrichment to resolve frontendQuestionId and difficulty with concurrency limit
        sem = asyncio.Semaphore(3)
        async def enrich_sub(sub):
            async with sem:
                try:
                    details = await self.get_problem_details(sub["titleSlug"])
                    if details:
                        sub["frontendQuestionId"] = details.get("questionFrontendId", "")
                        sub["difficulty"] = details.get("difficulty", "Medium")
                    else:
                        sub["frontendQuestionId"] = ""
                        sub["difficulty"] = "Medium"
                except Exception as e:
                    logger.error(f"Error enriching submission for {sub.get('titleSlug')}: {e}")
                    sub["frontendQuestionId"] = ""
                    sub["difficulty"] = "Medium"
                return sub

        tasks = [enrich_sub(sub) for sub in submissions]
        enriched_submissions = await asyncio.gather(*tasks)
        return enriched_submissions

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
        try:
            from src.services.redis_cache import cache_manager
            cached = await cache_manager.get(f"problem_details:{title_slug}")
            if cached and isinstance(cached, dict):
                return cached
        except Exception as e:
            logger.error(f"Error reading problem_details cache for {title_slug}: {e}")

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
        
        details = data["question"]
        try:
            from src.services.redis_cache import cache_manager
            await cache_manager.set(f"problem_details:{title_slug}", details, expire_seconds=604800)
        except Exception as e:
            logger.error(f"Error writing problem_details cache for {title_slug}: {e}")

        return details

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

    async def search_questions(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Searches LeetCode for questions matching a given keyword query using searchKeywords.
        """
        graphql_query = """
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
        filters = {"searchKeywords": query}
        data = await self._query(graphql_query, {
            "categorySlug": "",
            "limit": limit,
            "skip": 0,
            "filters": filters
        })
        if not data or not data.get("problemsetQuestionList"):
            return []
        return data["problemsetQuestionList"].get("questions", [])

    async def resolve_problem_query(self, query: str) -> List[Dict[str, Any]]:
        """
        Tries to resolve a problem search query (number, slug, or title) into a list of matches.
        - If query is a digit (e.g. "1"), searches and returns exact match where frontendQuestionId matches.
        - Otherwise, tries direct slug resolution (replacing spaces with hyphens, lowercase).
        - If direct slug is invalid, falls back to search_questions fuzzy results.
        - If fuzzy search results do not contain any close matches, falls back to Groq AI typo correction.
        """
        cleaned_query = query.strip()
        if not cleaned_query:
            return []

        # 1. Check if it's a number
        if cleaned_query.isdigit():
            # Search for the number
            results = await self.search_questions(cleaned_query, limit=10)
            exact_matches = [q for q in results if q.get("frontendQuestionId") == cleaned_query]
            if exact_matches:
                return exact_matches
            return results

        # 2. Try direct titleSlug matching (replace spaces with hyphens)
        potential_slug = cleaned_query.lower().replace(" ", "-")
        # Clean double hyphens if any
        while "--" in potential_slug:
            potential_slug = potential_slug.replace("--", "-")
        
        try:
            # Check if this slug is valid
            details = await self.get_problem_details(potential_slug)
            if details:
                return [{
                    "frontendQuestionId": details.get("questionFrontendId", ""),
                    "title": details.get("title", ""),
                    "titleSlug": details.get("titleSlug", ""),
                    "difficulty": details.get("difficulty", "Medium"),
                    "isPaidOnly": details.get("isPaidOnly", False)
                }]
        except Exception:
            pass

        # 3. Fallback to fuzzy search
        results = await self.search_questions(cleaned_query, limit=5)

        # Check if we have a strong textual similarity match (ratio >= 0.6)
        has_strong_match = False
        for q in results:
            ratio = difflib.SequenceMatcher(None, cleaned_query.lower(), q["title"].lower()).ratio()
            if ratio >= 0.6:
                has_strong_match = True
                break

        # If we have a strong match, or if LeetCode search returned nothing, return what we have
        if has_strong_match or not results:
            return results

        # 4. Fallback to Groq AI typo correction
        try:
            prompt = f"""
You are an expert LeetCode problem matcher. A user typed the following search query representing a LeetCode problem, which may contain typos, misspellings, or poor spacing:
"{cleaned_query}"

Analyze this query and return ONLY the most likely official LeetCode problem name (e.g. "Two Sum", "3Sum", "Median of Two Sorted Arrays"). If it is a number, return the number.
Do not include any greeting, explanation, markdown formatting, or quotes. Just output the corrected name.
"""
            chat_completion = await self.groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a helpful LeetCode problem matching assistant."},
                    {"role": "user", "content": prompt}
                ],
                model="openai/gpt-oss-120b",
                temperature=0.0
            )
            corrected = chat_completion.choices[0].message.content.strip().replace('"', '')
            if corrected and corrected.lower() != cleaned_query.lower():
                logger.info(f"Fuzzy typo query '{cleaned_query}' corrected by AI to '{corrected}'")
                corrected_results = await self.search_questions(corrected, limit=5)
                if corrected_results:
                    return corrected_results
        except Exception as e:
            logger.error(f"Error resolving query via AI typo correction: {e}")

        return results
