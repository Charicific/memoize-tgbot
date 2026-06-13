import asyncio
import sys
import os

# Add src to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.leetcode import LeetCodeClient
from src.utils.formatters import clean_leetcode_html

async def main():
    print("[INFO] Initializing LeetCodeClient...")
    client = LeetCodeClient()
    
    try:
        # Test 1: Fetch Daily Challenge
        print("\n[TEST 1] Testing Daily Challenge Fetch...")
        daily = await client.get_daily_challenge()
        if daily:
            question = daily["question"]
            print(f"[OK] Daily Challenge Title: {question['title']}")
            print(f"[OK] Difficulty: {question['difficulty']}")
            print(f"[OK] Link: https://leetcode.com{daily['link']}")
            
            # Clean HTML description
            print("\n[TEST 2] Testing Description HTML Cleaning...")
            cleaned = clean_leetcode_html(question["content"])
            print(f"Cleaned snippet (first 300 chars):\n{cleaned[:300]}...")
        else:
            print("[FAIL] Failed to fetch daily challenge.")

        # Test 2: Fetch Public User Profile
        test_username = "ghost"
        print(f"\n[TEST 3] Testing User Profile Fetch for '{test_username}'...")
        profile = await client.get_user_profile(test_username)
        if profile:
            ranking = profile["profile"].get("ranking")
            submit_stats = profile.get("submitStats", {}).get("acSubmissionNum", [])
            total_solved = next((item["count"] for item in submit_stats if item["difficulty"] == "All"), 0)
            
            print(f"[OK] User: {profile['username']}")
            print(f"[OK] Global Rank: {ranking}")
            print(f"[OK] Total Solved: {total_solved}")
        else:
            print(f"[FAIL] Failed to fetch user profile for '{test_username}'.")

        # Test 3: Fetch Problemset questions
        print("\n[TEST 4] Testing Problemset Fetch (Easy list)...")
        questions = await client.get_problemset_questions(limit=5, difficulty="easy")
        if questions:
            print(f"[OK] Fetched {len(questions)} easy questions:")
            for q in questions:
                print(f" - #{q['frontendQuestionId']}: {q['title']} (Slug: {q['titleSlug']})")
        else:
            print("[FAIL] Failed to fetch problemset questions.")

    finally:
        await client.close()
        print("\n[INFO] Client closed.")

if __name__ == "__main__":
    asyncio.run(main())
