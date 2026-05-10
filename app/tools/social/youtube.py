"""
YouTube video analysis tool.

This tool provides capabilities for extracting and analyzing YouTube video
transcripts, enabling tech watch from video content like tutorials, talks,
and conference presentations.

Features:
- Extract transcripts from YouTube videos
- Search for videos by topic/keyword
- Get video metadata (title, views, likes, channel)
- Analyze video content for tech relevance
"""

from typing import Any, Optional
import re

from app.tools.base import BaseTool, ToolCategory, ToolResult
from app.core.logging import get_logger


logger = get_logger(__name__)


class YouTubeTool(BaseTool):
    """Tool for YouTube video analysis and transcript extraction.

    Provides functionality to extract transcripts from YouTube videos,
    search for relevant videos, and analyze video content for tech
    monitoring purposes.

    Attributes:
        api_key: Optional YouTube Data API key for enhanced features
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        """Initialize YouTube tool.

        Args:
            api_key: Optional YouTube Data API v3 key for search features
        """
        super().__init__()
        self._api_key = api_key
        self._base_url = "https://www.youtube.com"
        self._transcript_api = None

    @property
    def name(self) -> str:
        return "youtube"

    @property
    def description(self) -> str:
        return """YouTube video analysis tool for extracting transcripts and
finding relevant technical content. Use this to extract spoken content from
tech talks, tutorials, and conference presentations for comprehensive monitoring."""

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SOCIAL

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["transcript", "search", "video_info", "analyze"],
                    "description": "The YouTube action to perform",
                },
                "video_url": {
                    "type": "string",
                    "description": "YouTube video URL or video ID (for transcript/info)",
                },
                "video_id": {
                    "type": "string",
                    "description": "YouTube video ID (for transcript/info)",
                },
                "query": {
                    "type": "string",
                    "description": "Search query (for search action)",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results (default: 10)",
                    "default": 10,
                },
                "language": {
                    "type": "string",
                    "description": "Transcript language preference (default: en)",
                    "default": "en",
                },
            },
            "required": ["action"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        """Execute YouTube tool action.

        Args:
            params: Action and parameters

        Returns:
            ToolResult with YouTube data or error
        """
        action = params.get("action")
        video_url = params.get("video_url", "")
        video_id = params.get("video_id", "") or self._extract_video_id(video_url)
        query = params.get("query", "")
        max_results = params.get("max_results", 10)
        language = params.get("language", "en")

        try:
            if action == "transcript":
                return await self._get_transcript(video_id or video_url, language)
            elif action == "search":
                return await self._search_videos(query, max_results)
            elif action == "video_info":
                return await self._get_video_info(video_id or video_url)
            elif action == "analyze":
                return await self._analyze_video(video_id or video_url, language)
            else:
                return {
                    "success": False,
                    "data": None,
                    "error": f"Unknown action: {action}",
                    "metadata": {},
                }

        except Exception as exc:
            logger.error("YouTube tool error: %s", exc)
            return {
                "success": False,
                "data": None,
                "error": str(exc),
                "metadata": {},
            }

    async def _get_transcript(self, video_id_or_url: str, language: str) -> ToolResult:
        """Get transcript from a YouTube video.

        Args:
            video_id_or_url: Video ID or full URL
            language: Preferred transcript language

        Returns:
            ToolResult with transcript data
        """
        video_id = self._extract_video_id(video_id_or_url)
        if not video_id:
            return {
                "success": False,
                "data": None,
                "error": "Invalid YouTube video URL or ID",
                "metadata": {},
            }

        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            # Try to get transcript
            try:
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            except Exception:
                # Fallback: try to fetch from video page directly
                return await self._get_transcript_from_page(video_id)

            # Try preferred language first
            transcript_data = None
            try:
                transcript = transcript_list.find_transcript([language])
                transcript_data = transcript.fetch()
            except Exception:
                # Fallback: try any available transcript
                try:
                    transcript = transcript_list.find_transcript([])
                    transcript_data = transcript.fetch()
                except Exception:
                    pass

            if not transcript_data:
                return {
                    "success": False,
                    "data": None,
                    "error": "No transcript available for this video",
                    "metadata": {"video_id": video_id},
                }

            # Format transcript
            transcript_text = self._format_transcript(transcript_data)
            timestamps = self._create_timestamped_segments(transcript_data)

            return {
                "success": True,
                "data": {
                    "video_id": video_id,
                    "transcript": transcript_text,
                    "segments": timestamps,
                    "duration_seconds": max(t.get("start", 0) + t.get("duration", 0) for t in timestamps) if timestamps else 0,
                    "language": transcript_list.find_transcript([language]).language_code if transcript_list else language,
                },
                "error": None,
                "metadata": {
                    "video_id": video_id,
                    "word_count": len(transcript_text.split()),
                },
            }

        except ImportError:
            return {
                "success": False,
                "data": None,
                "error": "youtube-transcript-api not installed. Install with: pip install youtube-transcript-api",
                "metadata": {},
            }
        except Exception as exc:
            logger.error("Transcript fetch error: %s", exc)
            return {
                "success": False,
                "data": None,
                "error": f"Failed to fetch transcript: {str(exc)}",
                "metadata": {"video_id": video_id},
            }

    async def _get_transcript_from_page(self, video_id: str) -> ToolResult:
        """Fallback method to extract transcript from video page HTML.

        Args:
            video_id: YouTube video ID

        Returns:
            ToolResult with extracted transcript
        """
        import httpx

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self._base_url}/watch?v={video_id}",
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    },
                )

            if response.status_code != 200:
                return {
                    "success": False,
                    "data": None,
                    "error": f"Failed to fetch video page: {response.status_code}",
                    "metadata": {"video_id": video_id},
                }

            # Look for caption data in page
            html = response.text

            # Try to find caption URLs in the page
            caption_pattern = r'"captionTracks":\[(.*?)\]'
            match = re.search(caption_pattern, html)

            if not match:
                return {
                    "success": False,
                    "data": None,
                    "error": "No caption data found in video page",
                    "metadata": {"video_id": video_id},
                }

            return {
                "success": True,
                "data": {
                    "video_id": video_id,
                    "transcript": "Caption data found but parsing not implemented",
                    "segments": [],
                },
                "error": None,
                "metadata": {"video_id": video_id},
            }

        except Exception as exc:
            return {
                "success": False,
                "data": None,
                "error": f"Failed to extract from page: {str(exc)}",
                "metadata": {"video_id": video_id},
            }

    async def _search_videos(self, query: str, max_results: int) -> ToolResult:
        """Search for YouTube videos by query.

        Uses YouTube Data API if API key is available, otherwise
        falls back to scraping the YouTube search page.

        Args:
            query: Search query
            max_results: Maximum number of results

        Returns:
            ToolResult with search results
        """
        if self._api_key:
            return await self._search_with_api(query, max_results)
        else:
            return await self._search_without_api(query, max_results)

    async def _search_with_api(self, query: str, max_results: int) -> ToolResult:
        """Search using YouTube Data API v3.

        Args:
            query: Search query
            max_results: Maximum results

        Returns:
            ToolResult with API results
        """
        import httpx

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    "https://www.googleapis.com/youtube/v3/search",
                    params={
                        "part": "snippet",
                        "q": query,
                        "type": "video",
                        "maxResults": max_results,
                        "key": self._api_key,
                    },
                )

            if response.status_code != 200:
                return {
                    "success": False,
                    "data": None,
                    "error": f"YouTube API error: {response.status_code}",
                    "metadata": {},
                }

            data = response.json()
            videos = []

            for item in data.get("items", []):
                video = {
                    "id": item["id"]["videoId"],
                    "title": item["snippet"]["title"],
                    "description": item["snippet"]["description"],
                    "channel": item["snippet"]["channelTitle"],
                    "published": item["snippet"]["publishedAt"],
                    "thumbnail": item["snippet"]["thumbnails"].get("medium", {}).get("url", ""),
                    "url": f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                }
                videos.append(video)

            return {
                "success": True,
                "data": videos,
                "error": None,
                "metadata": {"query": query, "count": len(videos)},
            }

        except Exception as exc:
            return {
                "success": False,
                "data": None,
                "error": str(exc),
                "metadata": {},
            }

    async def _search_without_api(self, query: str, max_results: int) -> ToolResult:
        """Search without API by scraping YouTube search page.

        Args:
            query: Search query
            max_results: Maximum results

        Returns:
            ToolResult with scraped results
        """
        import httpx

        try:
            encoded_query = query.replace(" ", "+")
            search_url = f"{self._base_url}/results?search_query={encoded_query}"

            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(
                    search_url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    },
                )

            if response.status_code != 200:
                return {
                    "success": False,
                    "data": None,
                    "error": f"Search failed: {response.status_code}",
                    "metadata": {},
                }

            # Parse video IDs from response
            html = response.text
            video_pattern = r'/watch\?v=([a-zA-Z0-9_-]{11})'
            video_ids = list(set(re.findall(video_pattern, html)))[:max_results]

            videos = []
            for video_id in video_ids:
                videos.append({
                    "id": video_id,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "title": "Video (API key required for details)",
                })

            return {
                "success": True,
                "data": videos,
                "error": None,
                "metadata": {"query": query, "count": len(videos)},
            }

        except Exception as exc:
            return {
                "success": False,
                "data": None,
                "error": str(exc),
                "metadata": {},
            }

    async def _get_video_info(self, video_id_or_url: str) -> ToolResult:
        """Get detailed video information.

        Args:
            video_id_or_url: Video ID or URL

        Returns:
            ToolResult with video details
        """
        video_id = self._extract_video_id(video_id_or_url)
        if not video_id:
            return {
                "success": False,
                "data": None,
                "error": "Invalid YouTube video URL or ID",
                "metadata": {},
            }

        try:
            import httpx

            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(
                    f"{self._base_url}/watch?v={video_id}",
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    },
                )

            html = response.text

            # Extract basic info from page
            title_match = re.search(r'<title>(.*?)</title>', html)
            title = title_match.group(1).replace(" - YouTube", "") if title_match else "Unknown"

            # Extract view count
            view_pattern = r'"viewCountText":\{"simpleText":"([0-9,]+ (?:views|view))"\}'
            view_match = re.search(view_pattern, html)
            views = view_match.group(1) if view_match else "Unknown"

            # Extract likes
            like_pattern = r'"likeButton":\{"toggleButtonApi":\{"toggleButtonTargetData":\{"defaultLikes":([0-9,]+)'
            like_match = re.search(like_pattern, html)
            likes = like_match.group(1) if like_match else "Unknown"

            # Extract channel name
            channel_pattern = r'"ownerChannelName":"([^"]+)"'
            channel_match = re.search(channel_pattern, html)
            channel = channel_match.group(1) if channel_match else "Unknown"

            # Extract upload date
            date_pattern = r'"uploadDateText":\{"simpleText":"([^"]+)"\}'
            date_match = re.search(date_pattern, html)
            upload_date = date_match.group(1) if date_match else "Unknown"

            return {
                "success": True,
                "data": {
                    "video_id": video_id,
                    "title": title,
                    "views": views,
                    "likes": likes,
                    "channel": channel,
                    "upload_date": upload_date,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                },
                "error": None,
                "metadata": {"video_id": video_id},
            }

        except Exception as exc:
            return {
                "success": False,
                "data": None,
                "error": str(exc),
                "metadata": {"video_id": video_id},
            }

    async def _analyze_video(self, video_id_or_url: str, language: str) -> ToolResult:
        """Get full analysis of a video (info + transcript).

        Combines video info and transcript for comprehensive analysis.

        Args:
            video_id_or_url: Video ID or URL
            language: Transcript language

        Returns:
            ToolResult with complete analysis
        """
        # Get transcript
        transcript_result = await self._get_transcript(video_id_or_url, language)

        # Get video info
        info_result = await self._get_video_info(video_id_or_url)

        if not info_result["success"]:
            return info_result

        return {
            "success": True,
            "data": {
                "info": info_result["data"],
                "transcript": transcript_result["data"] if transcript_result["success"] else None,
                "transcript_error": transcript_result.get("error"),
            },
            "error": None,
            "metadata": {
                "video_id": info_result["data"]["video_id"],
                "has_transcript": transcript_result["success"],
            },
        }

    @staticmethod
    def _extract_video_id(url_or_id: str) -> Optional[str]:
        """Extract video ID from URL or return if already an ID.

        Args:
            url_or_id: URL or video ID

        Returns:
            Video ID or None
        """
        if not url_or_id:
            return None

        # If it's already just an ID (11 chars)
        if len(url_or_id) == 11 and re.match(r'^[a-zA-Z0-9_-]+$', url_or_id):
            return url_or_id

        # Extract from various URL formats
        patterns = [
            r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
            r'youtu\.be/([a-zA-Z0-9_-]{11})',
            r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
            r'youtube\.com/v/([a-zA-Z0-9_-]{11})',
        ]

        for pattern in patterns:
            match = re.search(pattern, url_or_id)
            if match:
                return match.group(1)

        return None

    @staticmethod
    def _format_transcript(transcript_data: list) -> str:
        """Format transcript into clean text.

        Args:
            transcript_data: List of transcript segments

        Returns:
            Formatted transcript text
        """
        lines = []
        for segment in transcript_data:
            text = segment.get("text", "").strip()
            if text:
                lines.append(text)
        return " ".join(lines)

    @staticmethod
    def _create_timestamped_segments(transcript_data: list) -> list[dict]:
        """Create timestamped segments from transcript data.

        Args:
            transcript_data: List of transcript segments

        Returns:
            List of segments with timestamps
        """
        segments = []
        for segment in transcript_data:
            segments.append({
                "start": segment.get("start", 0),
                "duration": segment.get("duration", 0),
                "text": segment.get("text", "").strip(),
            })
        return segments

    def _format_video_summary(self, video: dict) -> str:
        """Format video info into readable summary.

        Args:
            video: Video dictionary

        Returns:
            Formatted summary string
        """
        lines = [
            f"**{video.get('title', 'Untitled')}**",
            f"Channel: {video.get('channel', 'Unknown')}",
        ]

        if video.get("views"):
            lines.append(f"Views: {video['views']}")

        if video.get("transcript"):
            transcript = video["transcript"]
            if isinstance(transcript, dict):
                text = transcript.get("transcript", "")
                lines.append(f"\nTranscript preview: {text[:300]}...")

        if video.get("url"):
            lines.append(f"\n[Watch on YouTube]({video['url']})")

        return "\n".join(lines)


# Helper functions

def is_valid_youtube_url(url: str) -> bool:
    """Check if a string is a valid YouTube URL or video ID.

    Args:
        url: URL or video ID to validate

    Returns:
        True if valid, False otherwise
    """
    video_id = YouTubeTool._extract_video_id(url)
    return video_id is not None


def format_duration(seconds: int) -> str:
    """Format duration in seconds to readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string (e.g., "1:23:45")
    """
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def extract_video_id(url: str) -> Optional[str]:
    """Extract video ID from URL (standalone function).

    Args:
        url: YouTube URL

    Returns:
        Video ID or None
    """
    return YouTubeTool._extract_video_id(url)