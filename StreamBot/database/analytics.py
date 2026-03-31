import datetime
import logging
from typing import Any, Dict, Optional

import aiohttp

from .database import database

logger = logging.getLogger(__name__)

links_col = database["analytics_links"]
events_col = database["analytics_link_events"]
user_stats_col = database["analytics_user_stats"]

_geo_cache: Dict[str, dict] = {}


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _json_safe(value: Any) -> Any:
    """Convert Mongo/python objects (datetime, nested dict/list) to JSON-safe values."""
    if isinstance(value, datetime.datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=datetime.timezone.utc)
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


async def lookup_ip_geo(ip: str) -> dict:
    """Best-effort IP geolocation lookup with in-memory cache."""
    if not ip:
        return {}
    if ip in _geo_cache:
        return _geo_cache[ip]

    url = f"http://ip-api.com/json/{ip}?fields=status,country,regionName,city,zip,lat,lon,isp,org,as,query"
    try:
        timeout = aiohttp.ClientTimeout(total=2.5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return {}
                data = await resp.json()
                if data.get("status") != "success":
                    return {}
                geo = {
                    "country": data.get("country"),
                    "region": data.get("regionName"),
                    "city": data.get("city"),
                    "zip": data.get("zip"),
                    "lat": data.get("lat"),
                    "lon": data.get("lon"),
                    "isp": data.get("isp"),
                    "org": data.get("org"),
                    "as": data.get("as"),
                }
                _geo_cache[ip] = geo
                return geo
    except Exception:
        return {}


async def record_link_generated(
    *,
    encoded_id: str,
    user_id: int,
    file_name: str,
    file_size: int,
    source: str,
    user_profile: Optional[Dict[str, Any]] = None,
) -> bool:
    """Persist link creation metadata for dashboard analytics."""
    if not encoded_id or not isinstance(user_id, int):
        return False
    try:
        links_col.update_one(
            {"_id": encoded_id},
            {
                "$set": {
                    "user_id": user_id,
                    "file_name": file_name or "",
                    "file_size": int(file_size or 0),
                    "source": source,
                    "created_at": _now(),
                    "user_profile": {
                        "username": (user_profile or {}).get("username", ""),
                        "first_name": (user_profile or {}).get("first_name", ""),
                        "last_name": (user_profile or {}).get("last_name", ""),
                        "language_code": (user_profile or {}).get("language_code", ""),
                        "is_premium": bool((user_profile or {}).get("is_premium", False)),
                        "is_verified": bool((user_profile or {}).get("is_verified", False)),
                    },
                },
                "$setOnInsert": {
                    "click_count": 0,
                    "total_bytes_served": 0,
                },
            },
            upsert=True,
        )
        user_stats_col.update_one(
            {"_id": user_id},
            {
                "$inc": {"links_generated": 1},
                "$setOnInsert": {"first_seen_at": _now()},
                "$set": {
                    "last_seen_at": _now(),
                    "username": (user_profile or {}).get("username", ""),
                    "first_name": (user_profile or {}).get("first_name", ""),
                    "last_name": (user_profile or {}).get("last_name", ""),
                    "language_code": (user_profile or {}).get("language_code", ""),
                    "is_premium": bool((user_profile or {}).get("is_premium", False)),
                    "is_verified": bool((user_profile or {}).get("is_verified", False)),
                },
            },
            upsert=True,
        )
        return True
    except Exception as e:
        logger.error(f"record_link_generated failed for {encoded_id}: {e}", exc_info=True)
        return False


async def record_link_access(
    *,
    encoded_id: str,
    request_path: str,
    ip: str,
    user_agent: str,
    bytes_served: int,
) -> bool:
    """Record a link access event including IP and geolocation."""
    try:
        link_doc = links_col.find_one({"_id": encoded_id}, {"user_id": 1, "file_name": 1, "file_size": 1, "source": 1})
        if not link_doc:
            return False
        user_id = link_doc.get("user_id")
        geo = await lookup_ip_geo(ip)
        now = _now()

        events_col.insert_one(
            {
                "encoded_id": encoded_id,
                "user_id": user_id,
                "request_path": request_path,
                "ip": ip,
                "user_agent": user_agent or "",
                "geo": geo,
                "bytes_served": int(bytes_served or 0),
                "created_at": now,
            }
        )

        links_col.update_one(
            {"_id": encoded_id},
            {"$inc": {"click_count": 1, "total_bytes_served": int(bytes_served or 0)}, "$set": {"last_accessed_at": now}},
        )
        user_stats_col.update_one(
            {"_id": user_id},
            {
                "$inc": {"total_clicks": 1, "total_bytes_served": int(bytes_served or 0)},
                "$set": {"last_seen_at": now},
                "$setOnInsert": {"first_seen_at": now},
            },
            upsert=True,
        )
        return True
    except Exception as e:
        logger.error(f"record_link_access failed for {encoded_id}: {e}", exc_info=True)
        return False


async def get_link_owner_user_id(encoded_id: str) -> Optional[int]:
    """Return owner user_id for a generated link if known."""
    if not encoded_id:
        return None
    try:
        doc = links_col.find_one({"_id": encoded_id}, {"user_id": 1})
        if not doc:
            return None
        uid = doc.get("user_id")
        return int(uid) if isinstance(uid, int) else None
    except Exception as e:
        logger.error(f"get_link_owner_user_id failed for {encoded_id}: {e}", exc_info=True)
        return None


async def get_dashboard_data(
    *,
    search: str = "",
    user_id: Optional[int] = None,
    start_dt: Optional[datetime.datetime] = None,
    end_dt: Optional[datetime.datetime] = None,
    links_page: int = 1,
    links_page_size: int = 50,
    events_page: int = 1,
    events_page_size: int = 50,
    users_page: int = 1,
    users_page_size: int = 50,
) -> Dict[str, Any]:
    """Assemble dashboard data with filters, graph series, and detailed logs."""
    try:
        links_page = max(1, int(links_page or 1))
        events_page = max(1, int(events_page or 1))
        users_page = max(1, int(users_page or 1))
        links_page_size = max(10, min(int(links_page_size or 50), 200))
        events_page_size = max(10, min(int(events_page_size or 50), 200))
        users_page_size = max(10, min(int(users_page_size or 50), 200))
        links_skip = (links_page - 1) * links_page_size
        events_skip = (events_page - 1) * events_page_size
        users_skip = (users_page - 1) * users_page_size

        date_match = {}
        if start_dt:
            if getattr(start_dt, "tzinfo", None) is None:
                start_dt = start_dt.replace(tzinfo=datetime.timezone.utc)
            date_match["$gte"] = start_dt
        if end_dt:
            if getattr(end_dt, "tzinfo", None) is None:
                end_dt = end_dt.replace(tzinfo=datetime.timezone.utc)
            date_match["$lte"] = end_dt

        link_query: Dict[str, Any] = {}
        event_query: Dict[str, Any] = {}
        if user_id is not None:
            link_query["user_id"] = user_id
            event_query["user_id"] = user_id
        if date_match:
            link_query["created_at"] = date_match
            event_query["created_at"] = date_match
        if search:
            regex = {"$regex": search, "$options": "i"}
            link_query["$or"] = [{"file_name": regex}, {"_id": regex}]

        total_users = user_stats_col.count_documents({})
        total_links = links_col.count_documents(link_query)
        total_events = events_col.count_documents(event_query)
        bw = list(events_col.aggregate([{"$match": event_query}, {"$group": {"_id": None, "bytes": {"$sum": "$bytes_served"}}}]))
        total_bw = int((bw[0].get("bytes") if bw else 0) or 0)

        links = list(
            links_col.find(link_query, {"_id": 1, "user_id": 1, "file_name": 1, "file_size": 1, "source": 1, "click_count": 1, "total_bytes_served": 1, "created_at": 1, "last_accessed_at": 1, "user_profile": 1})
            .sort("created_at", -1)
            .skip(links_skip)
            .limit(links_page_size)
        )
        events = list(
            events_col.find(event_query, {"_id": 0, "encoded_id": 1, "user_id": 1, "request_path": 1, "ip": 1, "geo": 1, "bytes_served": 1, "created_at": 1})
            .sort("created_at", -1)
            .skip(events_skip)
            .limit(events_page_size)
        )

        clicks_by_day_pipeline = [
            {"$match": event_query},
            {
                "$group": {
                    "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                    "clicks": {"$sum": 1},
                    "bytes": {"$sum": "$bytes_served"},
                }
            },
            {"$sort": {"_id": 1}},
        ]
        clicks_by_day = list(events_col.aggregate(clicks_by_day_pipeline))

        users = list(
            user_stats_col.find(
                {},
                {
                    "_id": 1,
                    "links_generated": 1,
                    "total_clicks": 1,
                    "total_bytes_served": 1,
                    "last_seen_at": 1,
                    "first_seen_at": 1,
                    "username": 1,
                    "first_name": 1,
                    "last_name": 1,
                    "language_code": 1,
                    "is_premium": 1,
                    "is_verified": 1,
                },
            )
            .sort("total_clicks", -1)
            .skip(users_skip)
            .limit(users_page_size)
        )

        return {
            "summary": {
                "total_users": total_users,
                "total_links": total_links,
                "total_clicks": total_events,
                "total_bandwidth_bytes": total_bw,
            },
            "links": _json_safe(links),
            "events": _json_safe(events),
            "users": _json_safe(users),
            "graph": _json_safe(clicks_by_day),
            "pagination": {
                "links": {
                    "page": links_page,
                    "page_size": links_page_size,
                    "total": total_links,
                    "total_pages": max(1, (total_links + links_page_size - 1) // links_page_size),
                },
                "events": {
                    "page": events_page,
                    "page_size": events_page_size,
                    "total": total_events,
                    "total_pages": max(1, (total_events + events_page_size - 1) // events_page_size),
                },
                "users": {
                    "page": users_page,
                    "page_size": users_page_size,
                    "total": total_users,
                    "total_pages": max(1, (total_users + users_page_size - 1) // users_page_size),
                },
            },
        }
    except Exception as e:
        logger.error(f"get_dashboard_data failed: {e}", exc_info=True)
        return {"summary": {}, "links": [], "events": [], "users": [], "graph": []}


async def get_user_detail(user_id: int) -> Dict[str, Any]:
    """Return full detail for one user: profile, subscription, links, and per-link event summary."""
    try:
        profile = user_stats_col.find_one({"_id": user_id}) or {}

        # Subscription record (use module-level database ref)
        sub_doc = database["allowed_users"].find_one({"_id": user_id})
        sub_info: Dict[str, Any] = {}
        if sub_doc:
            sub_info = {
                "has_subscription": True,
                "expires_at": _json_safe(sub_doc.get("expires_at")),
                "start_at": _json_safe(sub_doc.get("start_at")),
                "unlimited": sub_doc.get("expires_at") is None,
            }
        else:
            # Check dynamic admins
            admin_doc = database["dynamic_admins"].find_one({"_id": user_id})
            sub_info = {
                "has_subscription": admin_doc is not None,
                "is_admin": admin_doc is not None,
                "expires_at": None,
                "unlimited": admin_doc is not None,
            }

        # All links for this user, newest first
        links = list(
            links_col.find(
                {"user_id": user_id},
                {"_id": 1, "file_name": 1, "file_size": 1, "source": 1,
                 "click_count": 1, "total_bytes_served": 1, "created_at": 1, "last_accessed_at": 1}
            ).sort("created_at", -1)
        )

        # Top IPs across all user links
        ip_pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": "$ip",
                "hits": {"$sum": 1},
                "bytes": {"$sum": "$bytes_served"},
                "last_seen": {"$max": "$created_at"},
                "country": {"$first": "$geo.country"},
                "city": {"$first": "$geo.city"},
            }},
            {"$sort": {"bytes": -1}},
            {"$limit": 20},
        ]
        top_ips = list(events_col.aggregate(ip_pipeline))

        # Daily activity
        graph_pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                "clicks": {"$sum": 1},
                "bytes": {"$sum": "$bytes_served"},
            }},
            {"$sort": {"_id": 1}},
        ]
        graph = list(events_col.aggregate(graph_pipeline))

        return {
            "profile": _json_safe(profile),
            "subscription": sub_info,
            "links": _json_safe(links),
            "top_ips": _json_safe(top_ips),
            "graph": _json_safe(graph),
        }
    except Exception as e:
        logger.error(f"get_user_detail failed for {user_id}: {e}", exc_info=True)
        return {"profile": {}, "subscription": {}, "links": [], "top_ips": [], "graph": []}


async def get_link_events(encoded_id: str) -> Dict[str, Any]:
    """Return full event breakdown for one link: per-IP aggregation + raw events."""
    try:
        link_doc = links_col.find_one(
            {"_id": encoded_id},
            {"file_name": 1, "file_size": 1, "source": 1, "click_count": 1,
             "total_bytes_served": 1, "created_at": 1, "last_accessed_at": 1, "user_id": 1}
        )
        if not link_doc:
            return {"link": None, "ip_breakdown": [], "events": [], "graph": []}

        # Per-IP aggregation
        ip_pipeline = [
            {"$match": {"encoded_id": encoded_id}},
            {"$group": {
                "_id": "$ip",
                "hits": {"$sum": 1},
                "bytes": {"$sum": "$bytes_served"},
                "first_seen": {"$min": "$created_at"},
                "last_seen": {"$max": "$created_at"},
                "country": {"$first": "$geo.country"},
                "region": {"$first": "$geo.region"},
                "city": {"$first": "$geo.city"},
                "isp": {"$first": "$geo.isp"},
                "user_agents": {"$addToSet": "$user_agent"},
            }},
            {"$sort": {"bytes": -1}},
        ]
        ip_breakdown = list(events_col.aggregate(ip_pipeline))
        # Limit user_agents list per IP to avoid bloat
        for row in ip_breakdown:
            uas = row.get("user_agents") or []
            row["user_agents"] = [ua for ua in uas if ua][:10]

        # Daily timeline
        graph_pipeline = [
            {"$match": {"encoded_id": encoded_id}},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                "hits": {"$sum": 1},
                "bytes": {"$sum": "$bytes_served"},
            }},
            {"$sort": {"_id": 1}},
        ]
        graph = list(events_col.aggregate(graph_pipeline))

        # Raw events (most recent 500)
        raw_events = list(
            events_col.find(
                {"encoded_id": encoded_id},
                {"_id": 0, "ip": 1, "geo": 1, "user_agent": 1, "bytes_served": 1, "created_at": 1}
            ).sort("created_at", -1).limit(500)
        )

        return {
            "link": _json_safe(link_doc),
            "ip_breakdown": _json_safe(ip_breakdown),
            "graph": _json_safe(graph),
            "events": _json_safe(raw_events),
        }
    except Exception as e:
        logger.error(f"get_link_events failed for {encoded_id}: {e}", exc_info=True)
        return {"link": None, "ip_breakdown": [], "events": [], "graph": []}
