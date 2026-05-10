import os
from googleapiclient.discovery import build
import isodate
import logging

logger = logging.getLogger(__name__)

def search_youtube_video(query):
    """
    Searches YouTube for the best educational video matching the given query.
    Returns a dictionary containing video url, title, duration, and summary.
    """
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        logger.warning("YOUTUBE_API_KEY is not set in environment variables.")
        return None

    try:
        youtube = build('youtube', 'v3', developerKey=api_key)
        
        # Search for the video
        request = youtube.search().list(
            part="snippet",
            maxResults=1,
            q=query + " educational tutorial",
            type="video",
            relevanceLanguage="en"
        )
        response = request.execute()

        if not response.get('items'):
            logger.info(f"No YouTube videos found for query: {query}")
            return None

        video_item = response['items'][0]
        video_id = video_item['id']['videoId']
        title = video_item['snippet']['title']
        description = video_item['snippet']['description']
        
        # Get exact duration of the selected video
        video_request = youtube.videos().list(
            part="contentDetails",
            id=video_id
        )
        video_response = video_request.execute()
        
        duration_str = "00:00"
        if video_response.get('items'):
            iso_duration = video_response['items'][0]['contentDetails']['duration']
            # Parse ISO 8601 duration (e.g., PT1H2M30S)
            parsed_duration = isodate.parse_duration(iso_duration)
            total_seconds = int(parsed_duration.total_seconds())
            mins, secs = divmod(total_seconds, 60)
            hours, mins = divmod(mins, 60)
            if hours > 0:
                duration_str = f"{hours}:{mins:02d}:{secs:02d}"
            else:
                duration_str = f"{mins:02d}:{secs:02d}"

        return {
            "title": title,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "summary": description[:500],  # Keep reasonable length for model
            "duration": duration_str
        }

    except Exception as e:
        logger.error(f"YouTube API Error for query '{query}': {e}")
        return None
