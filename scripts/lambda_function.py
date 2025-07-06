# Set environment variables if running locally:
# set -a && source .env && set +a
import os
import json
import time
import datetime
import logging
import requests
import boto3
import openai
from openai import OpenAI
from functools import wraps
import random

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load env vars
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
SERPAPI_KEY = os.environ["SERP_API_KEY"]
BUCKET = os.environ["BUCKET"]

AUTH_TOKEN = os.environ["AUTH_TOKEN"]
CT0 = os.environ["CT0"]
GUEST_ID = os.environ["GUEST_ID"]
PERSONALIZATION_ID = os.environ["PERSONALIZATION_ID"]
BEARER_TOKEN = os.environ["BEARER_TOKEN"]
QUERY_ID = os.environ["QUERY_ID"]
MAX_TWEETS = 200
MAX_HEADLINES = 10

RULES = """Rules:
1. DO NOT include the poster or the media outlet as one of the three people, unless the news is about the poster/media outlet itself.
2. It MUST be specific people, places, companies, or events. It CANNOT be vague concepts or technologies, unless a SPECIFIC person or entity is named.
For example, DO NOT include "AI" or "Biotechnology". Instead, you should include the SPECIFIC COMPANY OR PERSON.
3. Note that if an entity is only mentioned a couple times and it's by the same poster, that is less compelling than if multiple different posters have mentioned it.
4. Ensure that not all three entities are too tightly related. For example, ["Elon Musk", "Tesla", "SpaceX"] would NOT be acceptable. Only pick 2 of those 3."""


if "AWS_PROFILE" in os.environ:
    session = boto3.Session(profile_name=os.environ["AWS_PROFILE"])
    s3 = session.client("s3")
else:
    s3 = boto3.client("s3")


def retry_on_exception(max_retries=1, excluded_exceptions=(), delay=5):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except excluded_exceptions as e:
                    # Don't retry for excluded exceptions
                    raise e
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning("Retrying %s after error (attempt %d/%d): %s", 
                                     func.__name__, attempt + 1, max_retries + 1, e)
                        
                        # Extract feedback from RuntimeError for entity extraction
                        if "Feedback:" in str(e) and len(args) > 0:
                            feedback = str(e).replace("Feedback: ", "")
                            # Create new args with feedback
                            new_args = list(args)
                            if len(new_args) > 1:
                                new_args[1] = feedback  # Replace feedback parameter
                            else:
                                new_args.append(feedback)  # Add feedback parameter
                            args = tuple(new_args)
                        
                        time.sleep(delay)
                    else:
                        logger.error("Failed %s after %d attempts. Last error: %s", 
                                   func.__name__, max_retries + 1, e)
                        raise last_exception
            
        return wrapper
    return decorator


def cache_to_s3(key_prefix, key_suffix=".json", data_extractor=None, cache_condition=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
            
            # Generate cache key based on function arguments
            if args:
                # Include all string arguments in the cache key
                arg_parts = [str(arg)[:20] for arg in args]
                if arg_parts:
                    cache_key = f"{today}/{key_prefix}-{'-'.join(arg_parts)}{key_suffix}"
                else:
                    cache_key = f"{today}/{key_prefix}{key_suffix}"
            else:
                # For functions without arguments
                cache_key = f"{today}/{key_prefix}{key_suffix}"
            
            # Try to load from cache
            try:
                logger.info("Checking S3 for cached %s (args: %s): s3://%s/%s", key_prefix, args, BUCKET, cache_key)
                response = s3.get_object(Bucket=BUCKET, Key=cache_key)
                cached_data = json.loads(response["Body"].read().decode("utf-8"))
                logger.info("Using cached %s from S3", key_prefix)
                
                # Extract data if needed
                if data_extractor:
                    return data_extractor(cached_data)
                return cached_data
                
            except s3.exceptions.NoSuchKey:
                logger.info("No cached %s found. Executing function...", key_prefix)
            except Exception as e:
                logger.warning("Error checking S3 for cached %s: %s", key_prefix, e)
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Check if we should cache the result
            if cache_condition and not cache_condition(result):
                logger.info("Skipping cache for %s due to condition", key_prefix)
                return result
            
            # Prepare data for caching
            data_to_cache = result
            if data_extractor:
                # If we have a data extractor, we need to store the full result
                # but return the extracted part
                data_to_cache = result
            
            # Save to S3
            try:
                s3.put_object(
                    Bucket=BUCKET,
                    Key=cache_key,
                    Body=json.dumps(data_to_cache, indent=2).encode("utf-8"),
                    ContentType="application/json"
                )
                logger.info("Saved %s to S3: %s", key_prefix, cache_key)
            except Exception as e:
                logger.warning("Failed to save %s to S3: %s", key_prefix, e)
            
            return result
        return wrapper
    return decorator


def build_twitter_payload(cursor=None):
    variables = {
        "count": 100,
        "includePromotedContent": True,
        "latestControlAvailable": True,
        "requestContext": "launch",
        "seenTweetIds": []
    }
    if cursor:
        variables["cursor"] = cursor

    return {
        "variables": variables,
        "features": {
            "rweb_video_screen_enabled": False,
            "payments_enabled": False,
            "profile_label_improvements_pcf_label_in_post_enabled": True,
            "rweb_tipjar_consumption_enabled": True,
            "verified_phone_label_enabled": False,
            "creator_subscriptions_tweet_preview_api_enabled": True,
            "responsive_web_graphql_timeline_navigation_enabled": True,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "premium_content_api_read_enabled": False,
            "communities_web_enable_tweet_community_results_fetch": True,
            "c9s_tweet_anatomy_moderator_badge_enabled": True,
            "responsive_web_grok_analyze_button_fetch_trends_enabled": False,
            "responsive_web_grok_analyze_post_followups_enabled": True,
            "responsive_web_jetfuel_frame": True,
            "responsive_web_grok_share_attachment_enabled": True,
            "articles_preview_enabled": True,
            "responsive_web_edit_tweet_api_enabled": True,
            "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
            "view_counts_everywhere_api_enabled": True,
            "longform_notetweets_consumption_enabled": True,
            "responsive_web_twitter_article_tweet_consumption_enabled": True,
            "tweet_awards_web_tipping_enabled": False,
            "responsive_web_grok_show_grok_translated_post": False,
            "responsive_web_grok_analysis_button_from_backend": True,
            "creator_subscriptions_quote_tweet_preview_enabled": False,
            "freedom_of_speech_not_reach_fetch_enabled": True,
            "standardized_nudges_misinfo": True,
            "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
            "longform_notetweets_rich_text_read_enabled": True,
            "longform_notetweets_inline_media_enabled": True,
            "responsive_web_grok_image_annotation_enabled": True,
            "responsive_web_enhance_cards_enabled": False
        },
        "queryId": QUERY_ID
    }


@retry_on_exception(max_retries=1)
@cache_to_s3(key_prefix="tweets-final", 
             data_extractor=lambda data: data["tweets"][:MAX_TWEETS],
             cache_condition=lambda result: len(result.get("tweets", [])) > 0)
def fetch_tweets():
    cookies = {
        'auth_token': AUTH_TOKEN,
        'ct0': CT0,
        'guest_id': GUEST_ID,
        'personalization_id': PERSONALIZATION_ID,
    }

    headers = {
        'Authorization': BEARER_TOKEN,
        'x-csrf-token': CT0,
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        'x-twitter-active-user': 'yes',
        'x-twitter-client-language': 'en',
        'Content-Type': 'application/json',
        'Referer': 'https://x.com/home'
    }

    url = f'https://x.com/i/api/graphql/{QUERY_ID}/HomeLatestTimeline'

    tweets = []
    cursor = None
    page = 1

    while len(tweets) < MAX_TWEETS:
        payload = build_twitter_payload(cursor)
        response = requests.post(url, headers=headers, cookies=cookies, json=payload)

        if not response.ok:
            logger.error("Twitter API error: %s", response.text)
            break

        data = response.json()
        instructions = data.get("data", {}).get("home", {}).get("home_timeline_urt", {}).get("instructions", [])
        found_cursor = False

        for instruction in instructions:
            entries = instruction.get("entries", [])
            for entry in entries:
                entry_id = entry.get("entryId", "")
                if entry_id.startswith("tweet-"):
                    result = entry.get("content", {}).get("itemContent", {}).get("tweet_results", {}).get("result", {})
                    full_text = result.get("legacy", {}).get("full_text")
                    user = result.get("core", {}).get("user_results", {}).get("result", {}).get("core", {})
                    screen_name = user.get("screen_name")
                    name = user.get("name")
                    if full_text:
                        tweets.append(f"{name} (@{screen_name}): {full_text}")
                        logger.info("Fetched tweet: %s (@%s): %s", name, screen_name, full_text[:100].replace("\n", " "))
                elif entry_id.startswith("cursor-bottom-"):
                    cursor = entry.get("content", {}).get("value")
                    found_cursor = True

        if not found_cursor:
            break

        time.sleep(1)
        page += 1

    if not tweets:
        raise RuntimeError("There were no tweets fetched")

    return {"tweets": tweets}


@cache_to_s3(key_prefix="news", 
             data_extractor=lambda data: extract_headlines_from_serp_response(data),
             cache_condition=lambda result: len(result.get("news_results", [])) > 0)
def get_recent_headlines(entity):
    # Fetch from SerpApi
    params = {
        "engine": "google_news",
        "q": entity,
        "hl": "en",
        "gl": "us",
        "api_key": SERPAPI_KEY,
    }

    try:
        response = requests.get("https://serpapi.com/search", params=params, timeout=10)
        serp_response = response.json()
    except Exception as e:
        logger.error("Failed to fetch news for %s from SerpApi: %s", entity, e)
        return []

    return serp_response


def extract_headlines_from_serp_response(serp_response):
    """Extract recent headlines from SerpApi response"""
    headlines = []
    now = datetime.datetime.utcnow()

    for result in serp_response.get("news_results", []):
        try:
            date_str = result["date"].split(",")[0]
            news_date = datetime.datetime.strptime(date_str, "%m/%d/%Y")
            if (now - news_date).days <= 1:
                headlines.append(result["title"])
        except:
            continue

    return headlines[:MAX_HEADLINES]


def format_entities_prompt(tweets, feedback=None):
    feedback_str = f"\n\nIMPORTANT, YOU PREVIOUSLY MADE THIS MISTAKE: {feedback}" if feedback is not None else ""

    if feedback_str:
        print(f"RECEIVED FEEDBACK: {feedback_str}")
    tweet_blob = "\n".join(tweets)
    return f"""Name the top 3 biggest announcements or most controversial people, places, companies, events that are referenced in these tweets.

{RULES}{feedback_str}

IMPORTANT: You MUST Respond in the following format and DO NOT SAY ANYTHING ADDITIONAL: ["Entity 1", "Entity 2", ...]

Tweets:
{tweet_blob}

Random nonce: {random.random()}"""


def format_relevance_prompt(entity, headlines, tweets):
    headline_blob = "\n".join(f"- {h}" for h in headlines)
    tweets_blob = "\n".join(tweets)
    return f"""Are any of the following headlines related to the tweets posted about {entity}? If not, respond saying that this is not related.

IMPORTANT: RESPOND WITH A SINGLE WORD, EITHER "RELEVANT" OR "IRRELEVANT". DO NOT SAY ANYTHING ADDITIONAL.

Headlines:
{headline_blob}

Tweets:
{tweets_blob}
"""


def format_summary_with_headlines_prompt(entity, headlines, tweets):
    headline_blob = "\n".join(f"- {h}" for h in headlines)
    tweets_blob = "\n".join(tweets)
    return f"""You are a friend explaining to me current events. Your output is intended for people reading a summary of latest events.
Summarize the main news around {entity} as referenced in the tweets below.
When you give your answer, DO NOT say anything like "based on the tweets". You should start your response with "{entity}".

I will provide a list of 10 headlines for additional context, and a bunch of tweets.
Many of the tweets may be unrelated to {entity} or the headlines. Please ONLY look at the tweets related to {entity}.
ONLY include information from headlines that could plausible related to the tweets. If the headlines look unrelated,
then just try to guess what's going on based on the tweets alone.

Headlines:
{headline_blob}

Tweets:
{tweets_blob}
"""


def format_summary_wo_headlines_prompt(entity, tweets):
    tweets_blob = "\n".join(tweets)
    return f"""You are a friend explaining to me current events. Your output is intended for people reading a summary of latest events.
Summarize the key announcement or controversy around {entity} as referenced in the tweets below.
When you give your answer, DO NOT say anything like "based on the tweets". You should start the first sentence of your response with "{entity}".
Do your best to infer what's going on based on the tweets below.
Many of the tweets may be unrelated to {entity}. Please ONLY look at the tweets related to {entity}.

Tweets:
{tweets_blob}
"""


def format_entities_validation_prompt(entities_str, tweets):
    tweet_sample = "\n".join(tweets[:50])
    return f"""Does the following list conform to these rules?

{RULES}

IMPORTANT: You MUST repsond with either VALID or feedback explaining which rule was violated in ONE sentence.
IMPORTANT: IF VALID, YOU MUST NOT SAY ANYTHING ADDITIONAL OTHER THAN "VALID".
IMPORTANT: DO NOT CHECK IF THE ENTITIES ARE REFERENCED IN THE TWEETS. AN ENTITY MAY NOT BE MENTIONED IN THE TWEETS AND THAT IS STILL VALID.

List: {entities_str}

Tweet sample that the entity list was derived from:
{tweet_sample}"""


@retry_on_exception(max_retries=3, excluded_exceptions=(openai.BadRequestError,))
def openai_entities_prompt(tweets, feedback=None):
    logger.info("Running entity extraction prompt")
    prompt = format_entities_prompt(tweets, feedback)
    resp = client.chat.completions.create(
        model="gpt-4.1",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    result = resp.choices[0].message.content
    logger.info("Entity extraction response:\n%s", result)
    validation_prompt = format_entities_validation_prompt(result, tweets)
    check = client.chat.completions.create(
        model="gpt-4.1",
        messages=[{"role": "user", "content": validation_prompt}],
        temperature=0,
    ).choices[0].message.content
    
    if check.lower() != "valid":
        # Pass the feedback to the retry decorator by raising an exception with the feedback
        raise RuntimeError(f"Feedback: {check}")
    
    return json.loads(result)


def _filter_tweets(entity, tweets):
    entity_matches = entity.split(" ")
    return [t for t in tweets if any(v in t for v in entity_matches)]


@retry_on_exception(max_retries=1)
def openai_news(entity, tweets):
    logger.info("Retrieving headlines about %s", entity)
    headlines = get_recent_headlines(entity)
    if not headlines:
        logger.info("No recent headlines found for %s", entity)
        return None

    tweets = _filter_tweets(entity, tweets)
    relevance_prompt = format_relevance_prompt(entity, headlines, tweets)
    logger.info("Running prompt to determine if headlines about %s relate to the tweets", entity)
    relevance = client.chat.completions.create(
        model="gpt-4.1" if len(tweets) < 50 else "gpt-3.5-turbo",
        messages=[{"role": "user", "content": relevance_prompt}],
        temperature=0,
    ).choices[0].message.content.strip().upper()

    logger.info("Relevance: %s", relevance)
    if relevance.lower() not in {"relevant", "irrelevant"}:
        raise ValueError(f"Unexpected relevance value: {relevance}")

    if relevance.lower() == "relevant":
        summary_prompt = format_summary_with_headlines_prompt(entity, headlines, tweets)
    else:
        summary_prompt = format_summary_wo_headlines_prompt(entity, tweets)

    logger.info("Running prompt to summarize the events about %s", entity)
    summary = client.chat.completions.create(
        model="gpt-4.1" if len(tweets) < 50 else "gpt-3.5-turbo",
        messages=[{"role": "user", "content": summary_prompt}],
        temperature=0,
    ).choices[0].message.content.strip()
    import pdb; pdb.set_trace()
    logger.info("Summary for %s:\n%s", entity, summary)
    return summary


def lambda_handler(event, context):
    tweets = fetch_tweets()
    
    try:
        entities = openai_entities_prompt(tweets)
    except openai.BadRequestError:
        logger.warning("Too many tweets - knocking off 30...")
        tweets = tweets[:-30]
        entities = openai_entities_prompt(tweets)

    latest_news = {}
    for entity in entities:
        latest_news[entity] = openai_news(entity, tweets)

    payload = {
        "timestamp": time.time(),
        "latest_news": latest_news
    }

    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    key = f'{today}/summary.json'
    logger.info("Uploading result to S3: s3://%s/%s", BUCKET, key)
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json.dumps(payload, indent=2).encode("utf-8"),
        ContentType="application/json"
    )

    return {"status": "success", "s3_key": key}


if __name__ == "__main__":
    lambda_handler({}, {})
