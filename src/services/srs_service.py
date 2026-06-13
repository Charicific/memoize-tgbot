import datetime
from typing import Dict, Any, Tuple
from src.services.supabase_db import db

class SRSService:
    @staticmethod
    def calculate_sm2(quality: int, ease: float, interval: int, reps: int) -> Tuple[float, int, int]:
        """
        Implements the SM-2 algorithm for spaced repetition.
        quality: 0 (completely forgot) to 5 (perfect response)
        ease: ease factor (starts at 2.5)
        interval: interval in days
        reps: repetition count
        """
        if quality >= 3:
            if reps == 0:
                interval = 1
            elif reps == 1:
                interval = 6
            else:
                interval = int(round(interval * ease))
            reps += 1
        else:
            reps = 0
            interval = 1

        ease = ease + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
        ease = max(1.3, ease)
        return ease, interval, reps

    async def log_review(self, telegram_id: int, problem_slug: str, quality: int) -> Dict[str, Any]:
        """
        Updates or creates an SRS review record for a given user and problem based on quality score (0-5).
        Returns the updated record.
        """
        existing = await db.get_srs_review(telegram_id, problem_slug)
        if existing:
            ease = existing["ease_factor"]
            interval = existing["interval"]
            reps = existing["repetitions"]
        else:
            ease = 2.5
            interval = 1
            reps = 0

        new_ease, new_interval, new_reps = self.calculate_sm2(quality, ease, interval, reps)
        next_review_date = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=new_interval)

        # Save to database
        record = await db.save_srs_review(
            telegram_id=telegram_id,
            problem_slug=problem_slug,
            ease_factor=new_ease,
            interval=new_interval,
            repetitions=new_reps,
            next_review_date=next_review_date,
            quality=quality
        )
        return record

srs_service = SRSService()
