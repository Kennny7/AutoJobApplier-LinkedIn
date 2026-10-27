import logging
from typing import Any, Dict, List
from core.portal_job_search import portal_job_search

logger = logging.getLogger(__name__)

class JobHunterSkill:
    """Skill for hunting jobs dynamically using web search feeds."""
    async def execute(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        location = params.get("location", "Remote")
        keywords = params.get("keywords", "AI/ML Engineer")
        experience = params.get("experience", "3+ years")
        limit = params.get("limit", 5)

        jobs = await portal_job_search.search_portals(
            keywords=keywords,
            location=location,
            experience=experience,
            limit=limit,
        )
        return {
            "success": True,
            "jobs": jobs,
            "total": len(jobs),
            "location": location,
            "keywords": keywords,
        }
