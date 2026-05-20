import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'streamflix.settings')
django.setup()

import requests
import json
from datetime import datetime
from django.db import transaction
from api.models import Movie, Genre, Country, Actor, Role
from api.services import (
    fetch_raw_nuxt_data,
    get_trailer_url,
    get_description,
    extract_cast_from_raw,
    fallback_name_from_detail_path
)
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import logging

logger = logging.getLogger(__name__)

lock = threading.Lock()


HEADERS = {
    "Host": "h5-api.aoneroom.com",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.5",
    "Content-Type": "application/json",
    "Referer": "https://moviebox.ph/",
    "X-Client-Info": '{"timezone":"Asia/Karachi"}',
    "X-Request-Lang": "en",
    "Origin": "https://moviebox.ph",
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1aWQiOjQ1NjI1MjIwNzU5MzU3ODUzOTIsImF0cCI6MywiZXh0IjoiMTc3ODAwMzE3OCIsImV4cCI6MTc4NTc3OTE3OCwiaWF0IjoxNzc4MDAyODc4fQ.-zojTZf3ZOsX7tdMJWrtACPRC-BkByUm8vgZ5vKmKx0",
    "Connection": "keep-alive"
}


def fetch_moviebox_search_results(type, sort="ForYou", page=1, perPage=30):
    url = "https://h5-api.aoneroom.com/wefeed-h5api-bff/subject/filter"

    payload = {
        "page": page,
        "perPage": perPage,
        "channelId": 1 if type == 'movies' else 2,
        "genre": "All",
        "country": "All",
        "year": "All",
        "sort": sort,
        "classify": "All"
    }

    response = requests.post(url, headers=HEADERS, json=payload, timeout=15)

    logger.info(f"[API] Status: {response.status_code}")

    response.raise_for_status()

    if not response.text.strip():
        raise RuntimeError("Empty response body")

    data = response.json()
    logger.info("[API] JSON parsed successfully")

    return data.get("data", {}).get("items", [])


@transaction.atomic
def process_single_movie(item):
    subject_id = item.get("subjectId")

    if not subject_id or not item.get("title") or not item.get("subjectType") or not item.get("cover"):
        logger.warning(f"[SKIP] Missing fields subjectId={subject_id}")
        return None

    movie, is_created = Movie.objects.get_or_create(subjectId=subject_id)

    movie.title = item.get("title", movie.title)
    movie.description = item.get("description", movie.description)
    movie.duration = item.get("duration") or movie.duration
    movie.rate = item.get("rate", movie.rate) or 0
    movie.imdbRate = float(item.get("imdbRatingValue", movie.imdbRate) or 0)
    movie.subjectType = item.get("subjectType", movie.subjectType)

    release_date = item.get("releaseDate")
    if release_date:
        try:
            movie.releaseDate = datetime.strptime(release_date, "%Y-%m-%d").date()
        except ValueError:
            logger.warning(f"[DATE] Invalid date: {release_date}")

    movie.detailPath = item.get("detailPath", movie.detailPath)
    movie.watch_url = item.get("watch_url", movie.watch_url)
    movie.corner = item.get("corner", movie.corner)
    movie.viewers = item.get("viewers", movie.viewers)
    movie.opItemId = item.get("opItemId", movie.opItemId)
    movie.seenStatus = item.get("seenStatus", movie.seenStatus)
    movie.content = item.get("content", movie.content)
    movie.deepLink = item.get("deepLink", movie.deepLink)
    movie.cover = item.get("cover", movie.cover)
    movie.image = item.get("image", movie.image)

    ops_data = item.get("ops")
    if isinstance(ops_data, str):
        try:
            movie.ops = json.loads(ops_data)
        except json.JSONDecodeError:
            movie.ops = {}
    else:
        movie.ops = ops_data or {}

    subtitles_data = item.get("subtitles")
    if isinstance(subtitles_data, dict):
        movie.subtitles = subtitles_data
    elif isinstance(subtitles_data, str):
        movie.subtitles = {"languages": subtitles_data}
    else:
        movie.subtitles = {}

    country_name = item.get("countryName")
    if country_name:
        country_obj, _ = Country.objects.get_or_create(name=country_name.strip())
        movie.country = country_obj
    else:
        movie.country = None


    genre_list = []
    genre_string = item.get("genre", "")
    if genre_string:
        for name in [g.strip() for g in genre_string.split(',') if g.strip()]:
            genre_obj, _ = Genre.objects.get_or_create(name=name)
            genre_list.append(genre_obj)
    movie.genre.set(genre_list)

    movie.save()

    if movie.detailPath:
        # full_movie_url = f"https://moviebox.ph/detail/{movie.detailPath}?id={movie.subjectId}&tab=movie"
        full_movie_url = f"https://moviebox.ph/detail/{movie.detailPath}?id={movie.subjectId}&scene=&page_from=type_filter_movie&type=/movie/detail&tab=movie"
        raw_data = fetch_raw_nuxt_data(full_movie_url)

        if raw_data:
            movie.trailer = get_trailer_url(raw_data)
            movie.description = get_description(raw_data)

            cast_data = extract_cast_from_raw(raw_data)

            if not cast_data:
                logger.warning("[CAST] No cast found")
            else:
                roles = []

                for cast in cast_data:
                    staff_id = cast.get("staffId")
                    name = cast.get("name")
                    character = cast.get("character")
                    detail_path = cast.get("detailPath", "")

                    if not name or not name.strip():
                        if detail_path:
                            name = fallback_name_from_detail_path(detail_path)

                    if not staff_id or not name or not name.strip():
                        continue

                    actor, created = Actor.objects.get_or_create(
                        staff_id=staff_id,
                        defaults={
                            "name": name.strip(),
                            "image_url": cast.get("avatarUrl", "") or ""
                        }
                    )

                    if not created and (not actor.name or not actor.name.strip()):
                        actor.name = name
                        actor.image_url = cast.get("avatarUrl", "") or ""
                        actor.save(update_fields=["name", "image_url"])

                    role, _ = Role.objects.get_or_create(
                        actor=actor,
                        character=character or ""
                    )

                    roles.append(role)

                movie.cast.set(roles)
                movie.save()

    return is_created, movie


def process_movie_item(type, sort="ForYou", page=1, perPage=50):
    created = 0
    updated = 0
    subject_ids = []

    items = [
        i for i in fetch_moviebox_search_results(type, page=page, sort=sort, perPage=perPage)
        if i.get("subjectType") == 1
    ]

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(process_single_movie, item) for item in items]

        processed_count = 0

        for future in as_completed(futures):
            try:
                result = future.result()
                if not result:
                    continue

                is_created, movie = result

                with lock:
                    subject_ids.append(movie.subjectId)
                    created += int(is_created)
                    updated += int(not is_created)

                processed_count += 1
                if processed_count % 10 == 0:
                    logger.info(f"[BATCH] Processed {processed_count}")
                    time.sleep(30)

            except Exception as e:
                logger.exception(f"[ERROR] {e}")

    return {
        "created": created,
        "updated": updated,
        "movies": Movie.objects.filter(subjectId__in=subject_ids)
    }

process_movie_item("movies")