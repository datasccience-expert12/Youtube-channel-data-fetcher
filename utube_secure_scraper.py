import streamlit as st
import googleapiclient.discovery
import pandas as pd
from datetime import datetime



# i added this part of the code(p1)
import re
import logging
import html

# Logging: for developer-only diagnostics (Streamlit Cloud logs). Do NOT print API keys.
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO)

# Allowlist regexes (strict formats)
API_KEY_REGEX = re.compile(r"^AIza[0-9A-Za-z\-_]{35}$")   # Google API key pattern (common case)
CHANNEL_ID_REGEX = re.compile(r"^UC[0-9A-Za-z\-_]{22}$") # YouTube channel id pattern (UC + 22 chars)

# Defensive length caps (absolute upper limit to avoid ultra-long inputs)
MAX_INPUT_LENGTH = 250

# till here (p1)


# ==========================================
# CONFIGURATION
# ==========================================
# Removed default API key and channel id
DEFAULT_API_KEY = ""
DEFAULT_CHANNEL_ID = ""



#i added this part of the code(p2)
def clean_input(s: str) -> str:
    """Trim whitespace and normalize. Do not alter characters beyond trimming."""
    if s is None:
        return ""
    return s.strip()

def is_plausible_api_key(key: str) -> bool:
    """Allowlist-based check for API key format + length guard."""
    if not key:
        return False
    if len(key) > MAX_INPUT_LENGTH:
        return False
    return bool(API_KEY_REGEX.fullmatch(key))

def is_plausible_channel_id(cid: str) -> bool:
    """Allowlist-based check for Channel ID format + length guard."""
    if not cid:
        return False
    if len(cid) > MAX_INPUT_LENGTH:
        return False
    return bool(CHANNEL_ID_REGEX.fullmatch(cid))

def looks_malicious(s: str) -> bool:
    """
    Extra heuristic checks (not primary defense). Returns True if input contains obvious
    injection-like tokens or control characters. We mainly rely on allowlist above.
    """
    if not s:
        return False
    # Reject strings containing whitespace inside (IDs and keys should not include spaces)
    if " " in s:
        return True
    # Control characters or null bytes
    if any(ord(ch) < 32 for ch in s):
        return True
    # Common SQL/command injection tokens (heuristic — allowlist is authoritative)
    suspicious_tokens = ["--", ";--", ";", "/*", "*/", "xp_", "drop ", "union ", " or ", " and ", "' or '1'='1", "\" or \"1\"=\"1"]
    low = s.lower()
    for token in suspicious_tokens:
        if token in low:
            return True
    return False

# till here(p2)




# ==========================================
# FUNCTIONS
# ==========================================

def get_channel_stats(youtube, channel_id):
    try:
        response = youtube.channels().list(
            id=channel_id,
            part='snippet,statistics,contentDetails'
        ).execute()
        
        if response['items']:
            item = response['items'][0]
            return {
                'title': item['snippet']['title'],
                'thumbnail': item['snippet']['thumbnails']['high']['url'],
                'subscribers': item['statistics']['subscriberCount'],
                'total_views': item['statistics']['viewCount'],
                'video_count': item['statistics']['videoCount'],
                'uploads_playlist': item['contentDetails']['relatedPlaylists']['uploads']
            }
    # except Exception as e:
    #     st.error(f"Error fetching channel info: {e}")
    # return None

    # i added (p4)
    except Exception:
     logger.exception("get_channel_stats failed for channel_id=%s", channel_id)
    st.error("Failed to fetch channel info. Please check the Channel ID and API key.")
    return None
# till here(p4)


def get_video_details(youtube, video_ids):
    all_stats = {}
    
    # Iterate over video_ids in chunks of 50
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i+50]
        
        # 1. The TRY block starts here
        try:
            response = youtube.videos().list(
                part="snippet,statistics",
                id=','.join(chunk)
            ).execute()
            
            for item in response.get('items', []):
                vid = item['id']
                snippet = item['snippet']
                stats = item['statistics']
                
                all_stats[vid] = {
                    'views': int(stats.get('viewCount', 0)),
                    'likes': int(stats.get('likeCount', 0)),
                    'comments': int(stats.get('commentCount', 0)),
                    'thumbnail': snippet['thumbnails']['high']['url'],
                    'tags': snippet.get('tags', [])
                }

        # 2. The EXCEPT block must align with the TRY block above
        except Exception:
            # 3. The code inside must be indented relative to 'except'
            logger.exception("get_video_details batch failed (videos chunk size=%d)", len(chunk))
            st.error("Failed to fetch video statistics. Try again or check API quota.")
            continue  # This skips to the next batch of 50 videos

    return all_stats


# def get_video_details(youtube, video_ids):
#     all_stats = {}
#     for i in range(0, len(video_ids), 50):
#         chunk = video_ids[i:i+50]
#         try:
#             response = youtube.videos().list(
#                 id=",".join(chunk),
#                 part="statistics,snippet"
#             ).execute()

#             for item in response['items']:
#                 vid = item['id']
#                 stats = item['statistics']
#                 snippet = item['snippet']
#                 all_stats[vid] = {
#                     'views': int(stats.get('viewCount', 0)),
#                     'likes': int(stats.get('likeCount', 0)),
#                     'comments': int(stats.get('commentCount', 0)),
#                     'thumbnail': snippet['thumbnails']['high']['url'],
#                     'tags': snippet.get('tags', [])
#                 }
#     #     except Exception as e:
#     #         st.error(f"Error fetching video stats batch: {e}")
#     # return all_stats

#     # i added (p5)
#         except Exception:
#          logger.exception("get_video_details batch failed (videos chunk size=%d)", len(chunk))
#     st.error("Failed to fetch video statistics. Try again or check API quota.")
#     continue
# return all_stats
# till here(p5)

def get_all_videos(api_key, channel_id):
    youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)

    channel_info = get_channel_stats(youtube, channel_id)
    if not channel_info:
        return None, None

    uploads_playlist_id = channel_info['uploads_playlist']
    
    videos_basic = []
    next_page_token = None

    status_text = st.empty()
    status_text.text("Fetching video list...")

    while True:
        playlist_response = youtube.playlistItems().list(
            playlistId=uploads_playlist_id,
            part='contentDetails,snippet',
            maxResults=50,
            pageToken=next_page_token
        ).execute()

        for item in playlist_response['items']:
            video_id = item['contentDetails']['videoId']
            title = item['snippet']['title']



            published_at = item['snippet']['publishedAt']

            try:
                date_obj = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ")
                date_str = date_obj.strftime("%Y-%m-%d")
            except:
                date_str = published_at



            videos_basic.append({
                'video_id': video_id,
                'title': title,
                'published_at': date_str,
                'publish_dt': date_obj
            })

        next_page_token = playlist_response.get('nextPageToken')
        if not next_page_token:
            break

    status_text.text(f"Found {len(videos_basic)} videos. Fetching detailed stats...")

    video_ids_list = [v['video_id'] for v in videos_basic]
    detailed_stats = get_video_details(youtube, video_ids_list)

    final_data = []
    for v in videos_basic:
        vid = v['video_id']
        stats = detailed_stats.get(vid, {})

        final_data.append({
            'Thumbnail': stats.get('thumbnail', ''),
            'Title': v['title'],
            'Published': v['published_at'],
            'Views': stats.get('views', 0),
            'Likes': stats.get('likes', 0),
            'Comments': stats.get('comments', 0),
            'Video ID': vid,
            'publish_dt': v['publish_dt']
        })

    status_text.empty()
    return channel_info, pd.DataFrame(final_data)

# ==========================================
# STREAMLIT UI LAYOUT
# ==========================================
st.set_page_config(page_title="YouTube Analytics Dashboard", layout="wide", page_icon="Hz")



# with st.sidebar:
#     st.header("⚙️ Settings")

#     # User must enter API key and Channel ID
#     api_key_input = st.text_input("API Key", value=DEFAULT_API_KEY, type="password")
#     channel_id_input = st.text_input("Channel ID", value=DEFAULT_CHANNEL_ID)

#     if st.button("Load Data", type="primary"):
#         if not api_key_input.strip() or not channel_id_input.strip():
#             st.error("Please enter both API Key and Channel ID.")
#         else:
#             with st.spinner("Scraping YouTube..."):
#                 channel_info, df = get_all_videos(api_key_input, channel_id_input)
#                 if channel_info and not df.empty:
#                     st.session_state['data'] = df
#                     st.session_state['channel'] = channel_info
#                 else:
#                     st.error("Could not fetch data. Check your API key or Channel ID.")




# i added (p3)
with st.sidebar:
    st.header("⚙️ Settings")

    # User must enter API key and Channel ID
    api_key_input = st.text_input("API Key", value=DEFAULT_API_KEY, type="password")
    channel_id_input = st.text_input("Channel ID", value=DEFAULT_CHANNEL_ID)

    if st.button("Load Data", type="primary"):
        # Normalize
        api_key = clean_input(api_key_input)
        channel_id = clean_input(channel_id_input)

        # Basic presence checks
        if not api_key or not channel_id:
            st.error("Both API Key and Channel ID are required.")
        # Length caps
        elif len(api_key) > MAX_INPUT_LENGTH or len(channel_id) > MAX_INPUT_LENGTH:
            st.error("Input is too long. Please enter valid API Key and Channel ID.")
            logger.warning("Rejected excessively long input (possible attack or paste mistake).")
        # Heuristic malicious tokens (extra precaution)
        elif looks_malicious(api_key) or looks_malicious(channel_id):
            st.error("Input contains disallowed characters or tokens.")
            logger.warning("Rejected input that looks malicious.")
        # Strict allowlist validation
        elif not is_plausible_api_key(api_key):
            st.error("API Key format invalid. Ensure you pasted the correct YouTube API key.")
            logger.info("API key format validation failed.")
        elif not is_plausible_channel_id(channel_id):
            st.error("Channel ID format invalid. Channel IDs typically start with 'UC' and are 24 characters long.")
            logger.info("Channel ID format validation failed.")
        else:
            # All validations passed; proceed
            with st.spinner("Scraping YouTube..."):
                try:
                    channel_info, df = get_all_videos(api_key, channel_id)
                except Exception as e:
                    # Log full technical detail for developer; do not expose to user
                    logger.exception("Unhandled error in get_all_videos")
                    st.error("An unexpected error occurred while fetching data. Please try again later.")
                    channel_info, df = None, None

                if channel_info and not (df is None) and not df.empty:
                    st.session_state['data'] = df
                    st.session_state['channel'] = channel_info
                else:
                    st.error("Could not fetch data. Check your API key and Channel ID.")

# till here (p3)


if 'data' in st.session_state:
    df = st.session_state['data']
    ch = st.session_state['channel']



    col1, col2 = st.columns([1, 4])
    with col1:
        st.image(ch['thumbnail'], width=150)



    with col2:
        st.title(ch['title'])
        st.write(f"**Subscribers:** {int(ch['subscribers']):,} | "
                 f"**Total Videos:** {ch['video_count']} | "
                 f"**Total Views:** {int(ch['total_views']):,}")

    st.divider()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Avg Views per Video", f"{int(df['Views'].mean()):,}")
    m2.metric("Most Viewed Video", f"{int(df['Views'].max()):,}")
    m3.metric("Avg Likes", f"{int(df['Likes'].mean()):,}")
    m4.metric("Total Likes", f"{int(df['Likes'].sum()):,}")

    st.divider()

    st.subheader("📺 Video Performance")

    st.dataframe(
        df,
        column_config={
            "Thumbnail": st.column_config.ImageColumn("Thumbnail", width="medium"),
            "Views": st.column_config.NumberColumn("Views", format="%d 👁️"),
            "Likes": st.column_config.NumberColumn("Likes", format="%d 👍"),
            "Comments": st.column_config.NumberColumn("Comments", format="%d 💬"),
            "publish_dt": None
        },
        use_container_width=True,
        hide_index=True,
        height=800
    )






    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("Download Data as CSV", csv, "youtube_stats_dashboard.csv", "text/csv")

else:
    st.info("👈 Enter API key & Channel ID in sidebar, then click **Load Data**.")
