import logging
import httpx
import time
from typing import Optional, Dict, Any
from aiogram import html
from src.config import settings

logger = logging.getLogger(__name__)

async def get_uptimerobot_stats() -> Optional[Dict[str, Any]]:
    """
    Fetches monitor status and uptime ratio from UptimeRobot.
    Returns a dict with 'status' (string), 'uptime' (string duration), and success=True,
    or None on error/not configured.
    """
    if not settings.UPTIMEROBOT_API_KEY:
        return None

    url = "https://api.uptimerobot.com/v2/getMonitors"
    payload = {
        "api_key": settings.UPTIMEROBOT_API_KEY,
        "format": "json",
        "logs": 1
    }

    if settings.UPTIMEROBOT_MONITOR_ID:
        payload["monitors"] = settings.UPTIMEROBOT_MONITOR_ID

    try:
        async with httpx.AsyncClient(http2=True, timeout=5.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code != 200:
                err_msg = f"HTTP status code {response.status_code}"
                logger.error(f"UptimeRobot API failed: {err_msg}")
                await _notify_failure(err_msg)
                return None

            data = response.json()
            if data.get("stat") != "ok":
                err_msg = f"Status not OK: {data.get('error', {}).get('message', str(data))}"
                logger.error(f"UptimeRobot API failed: {err_msg}")
                await _notify_failure(err_msg)
                return None

            monitors = data.get("monitors")
            if not monitors:
                err_msg = "No monitors returned"
                logger.error(f"UptimeRobot API failed: {err_msg}")
                await _notify_failure(err_msg)
                return None

            monitor = monitors[0]
            status_code = monitor.get("status")
            status_map = {
                0: "Paused",
                1: "Not checked yet",
                2: "Up ✅",
                8: "Seems down ⚠️",
                9: "Down ❌"
            }
            status_str = status_map.get(status_code, f"Unknown ({status_code})")

            # Calculate precise uptime duration if status is UP (2)
            formatted_uptime = "N/A"
            if status_code == 2:
                last_change = monitor.get("last_status_change")
                
                # Fallback to logs if last_status_change is missing (common for Monitor-Specific API Keys)
                if not last_change and "logs" in monitor:
                    for log in monitor["logs"]:
                        if log.get("type") == 2:  # Type 2 is 'Up' transition
                            last_change = log.get("datetime")
                            break
                            
                # Fallback to creation date if still missing
                if not last_change:
                    last_change = monitor.get("create_datetime")
                    
                if last_change:
                    try:
                        uptime_seconds = int(time.time() - int(last_change))
                        if uptime_seconds > 0:
                            formatted_uptime = _format_duration(uptime_seconds)
                    except Exception as parse_err:
                        logger.error(f"Error parsing status change time: {parse_err}")

            return {
                "status": status_str,
                "uptime": formatted_uptime,
                "name": monitor.get("friendly_name", "Memoize Bot"),
                "success": True
            }
    except Exception as e:
        err_msg = str(e)
        logger.error(f"Error fetching stats from UptimeRobot: {err_msg}")
        await _notify_failure(err_msg)
        return None

def _format_duration(seconds: int) -> str:
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")

    return " ".join(parts)

async def _notify_failure(error_msg: str):
    """
    Asynchronously notifies the administrative log channel of the UptimeRobot API failure.
    """
    try:
        from src.utils.logging_helper import send_log
        alert_msg = (
            f"⚠️ {html.bold('UptimeRobot API Call Failed')} ⚠️\n\n"
            f"• {html.bold('Error Detail:')} {html.code(html.quote(error_msg))}"
        )
        await send_log(alert_msg, disable_notification=False)
    except Exception as e:
        logger.error(f"Failed to send failure notification to log channel: {e}")
