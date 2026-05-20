import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import requests
from requests_html import HTMLSession
from django.db import transaction, close_old_connections
import threading
from api.models import Movie, Genre, Actor, Role, Country, TV_Series, Episode, Foryou
from django.utils.dateparse import parse_date
from bs4 import BeautifulSoup
import re
import time
import random
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

session = HTMLSession()
lock = threading.Lock()

HEADERS = {
    "Accept": "application/json",
    # "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.5",
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1aWQiOjQ1NjI1MjIwNzU5MzU3ODUzOTIsImF0cCI6MywiZXh0IjoiMTc3ODAwMzE3OCIsImV4cCI6MTc4NTc3OTE3OCwiaWF0IjoxNzc4MDAyODc4fQ.-zojTZf3ZOsX7tdMJWrtACPRC-BkByUm8vgZ5vKmKx0",
    "Content-Type": "application/json",
    "Connection": "keep-alive",
    "Origin": "https://moviebox.ph",
    "Referer": "https://moviebox.ph/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site",
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:146.0) Gecko/20100101 Firefox/146.0",
    "X-Client-Info": '{"timezone":"Asia/Karachi"}',
    "X-Request-Lang": "en"
}

def fetch_raw_nuxt_data(movie_url):
    try:
        total_delay = 15 + random.uniform(5.0, 10.0)
        time.sleep(total_delay)

        response = requests.get(movie_url, headers=HEADERS, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        script_tag = soup.find('script', id='__NUXT_DATA__')

        if not script_tag:
            logger.warning(f"[Nuxt] No __NUXT_DATA__ found for {movie_url}")
            return None

        return script_tag.string

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            logger.warning(f"[Nuxt] Rate limited: {movie_url}")
            time.sleep(10)
        else:
            logger.error(f"[Nuxt] HTTPError: {e}")

    except Exception as e:
        logger.exception(f"[Nuxt] Error: {e}")

    return None

def deobfuscate_nuxt_data(raw_data):
    if not raw_data:
        return None
    try:
        data = json.loads(raw_data)
    except json.JSONDecodeError:
        logger.error("[Deobfuscate] Invalid JSON")
        return None

    map_dict = {}

    for i, d in enumerate(data):
        if isinstance(d, str):
            map_dict[i] = d.strip().replace("// ", "//")
        elif isinstance(d, int):
            map_dict[i] = d

    for i, d in enumerate(data):
        if isinstance(d, dict):
            map_dict[i] = {k: map_dict.get(v) for k, v in d.items()}

    for i, d in enumerate(data):
        if isinstance(d, list):
            map_dict[i] = [map_dict.get(v) for v in d]

    final_dict = {}
    for i in data:
        if isinstance(i, dict):
            for k, v in i.items():
                final_dict[k] = map_dict.get(v)

    return final_dict


def get_trailer_url(raw_data):
    nuxt_data = deobfuscate_nuxt_data(raw_data)
    if nuxt_data:
        trailer_url = nuxt_data.get('videoAddress', {}).get('url')
        if not trailer_url:
            trailer_url = nuxt_data.get('trailer', {}).get('videoAddress', {}).get('url')
        return trailer_url
    return None

def get_description(raw_data):
    nuxt_data = deobfuscate_nuxt_data(raw_data)
    if nuxt_data:
        return nuxt_data.get('subject', {}).get('description')
    return None

def extract_cast_from_raw(raw_data):
    if not raw_data:
        return []

    try:
        data = json.loads(raw_data)
    except json.JSONDecodeError as e:
        logger.error(f"[CAST] JSON decode failed: {e}")
        return []

    index_map = {i: v for i, v in enumerate(data)}

    def resolve(val, depth=0):
        if depth > 50:
            return None
        if isinstance(val, int):
            return resolve(index_map.get(val), depth + 1)
        return val

    staff_indexes = None
    for item in data:
        if isinstance(item, list) and item and all(isinstance(x, int) for x in item) and len(item) > 5:
            staff_indexes = item
            break

    if not staff_indexes:
        return []

    cast = []
    for idx in staff_indexes:
        staff = index_map.get(idx)
        if not isinstance(staff, dict):
            continue

        cast.append({
            "staffId": resolve(staff.get("staffId")),
            "name": resolve(staff.get("name")),
            "character": resolve(staff.get("character")),
            "avatarUrl": resolve(staff.get("avatarUrl")),
            "detailPath": resolve(staff.get("detailPath")),
        })

    logger.info(f"[CAST] Total cast extracted: {len(cast)}")
    return cast

def fallback_name_from_detail_path(detail_path: str) -> str:
    if not detail_path:
        return ""

    base_path = detail_path.rsplit('-', 1)[0]
    parts = [p.title() for p in base_path.split('-')]
    return " ".join(parts)

def fetch_moviebox_search_results(type, sort="ForYou", page=1, perPage=50):
    url = "https://h5-api.aoneroom.com/wefeed-h5api-bff/subject/filter"

    payload = {
        "page": page,
        "perPage": perPage,
        "channelId": 1 if type == 'movies' else 2,
        "year": "All",
        "sort": sort
    }

    response = requests.post(url, headers=HEADERS, json=payload)
    response.raise_for_status()

    return response.json().get("data", {}).get("items", [])

def search_moviebox_subjects(keyword, limit=10):
    url = "https://h5-api.aoneroom.com/wefeed-h5api-bff/subject/search"

    payload = {"keyword": keyword, "page": 1, "perPage": limit}

    try:
        response = requests.post(url, headers=HEADERS, json=payload, timeout=10)
        response.raise_for_status()

        items = response.json().get("data", {}).get("items", [])
        subjects = [i for i in items if i.get("subjectType") in (1, 2)]

        logger.info(f"[SEARCH] Found {len(subjects)} subjects for '{keyword}'")
        return subjects

    except Exception as e:
        logger.exception(f"[SEARCH] Failed: {e}")
        return []


@transaction.atomic
def process_single_movie(item):
    subject_id = item.get("subjectId")
    if not subject_id:
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
            logger.warning(f"[MOVIE] Invalid release date: {release_date}")

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

    if is_created and movie.detailPath:
        logger.info(f"[SCRAPE] New movie: {movie.title}")

        full_movie_url = f"https://moviebox.ph/detail/{movie.detailPath}?id={movie.subjectId}&scene=&page_from=type_filter_movie&type=/movie/detail&tab=movie"
        raw_data = fetch_raw_nuxt_data(full_movie_url)

        if not raw_data:
            return is_created, movie

        trailer_url = get_trailer_url(raw_data)
        if trailer_url:
            movie.trailer = trailer_url

        description = get_description(raw_data)
        if description:
            movie.description = description

        movie_cast_data = extract_cast_from_raw(raw_data)
        if movie_cast_data:
            role_instances = []

            for cast in movie_cast_data:
                staff_id = cast.get("staffId")
                name = cast.get("name")

                if not staff_id or not name:
                    continue

                actor, _ = Actor.objects.get_or_create(
                    staff_id=staff_id,
                    defaults={"name": name, "image_url": cast.get("avatarUrl", "")}
                )

                role, _ = Role.objects.get_or_create(
                    actor=actor,
                    character=cast.get("character") or ""
                )

                role_instances.append(role)

            movie.cast.set(role_instances)

        movie.save()

    else:
        logger.info(f"[SKIP] Movie exists: {movie.title}")

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
                    logger.info(f"[MOVIE] Processed {processed_count}")
                    time.sleep(30)

            except Exception as e:
                logger.exception(f"[MOVIE] Error: {e}")

    return {
        "created": created,
        "updated": updated,
        "movies": Movie.objects.filter(subjectId__in=subject_ids)
    }

def get_trailer_url(raw_data):
    nuxt_data = deobfuscate_nuxt_data(raw_data)
    if isinstance(nuxt_data, dict):
        trailer_url = nuxt_data.get('videoAddress', {})
        if isinstance(trailer_url, dict):
            return trailer_url.get('url')
        return nuxt_data.get('trailer', {}).get('videoAddress', {}).get('url')
    return None

def get_description(raw_data):
    nuxt_data = deobfuscate_nuxt_data(raw_data)
    if isinstance(nuxt_data, dict):
        subject = nuxt_data.get('subject', {})
        if isinstance(subject, dict):
            return subject.get('description')
    return None

def get_seasons_and_episodes(raw_data):
    nuxt_data = deobfuscate_nuxt_data(raw_data)

    if isinstance(nuxt_data, dict):
        seasons = nuxt_data.get('seasons')

        result = []
        if isinstance(seasons, list):
            for season in seasons:
                season_number = season.get('se')
                episode_count = season.get('maxEp')
                if season_number and episode_count:
                    result.append({
                        "season": season_number,
                        "episodes": episode_count
                    })
        return result

def save_season_episode_data(subject_id, series, raw_data):
    seasons_data = get_seasons_and_episodes(raw_data)

    if not seasons_data:
        logger.warning(f"[SERIES] No seasons data: {subject_id}")
        return

    for season_info in seasons_data:
        season_num = season_info["season"]
        total_episodes = season_info["episodes"]

        for ep_num in range(1, total_episodes + 1):
            episode_instance, _ = Episode.objects.update_or_create(
                subjectId=subject_id,
                resourceId=None,
                episode=ep_num,
                season=season_num,
                defaults={
                    "title": f"Episode {ep_num}",
                    "resourceLink": series.detailPath or "",
                    "linkType": 2,
                    "uploadBy": "MB",
                    "codecName": "hevc",
                    "is_active": True,
                }
            )

            series.episode.add(episode_instance)

@transaction.atomic
def process_single_series(item):
    subject_id = item.get("subjectId")
    if not subject_id:
        return None

    series, is_created = TV_Series.objects.get_or_create(subjectId=subject_id)

    series.title = item.get("title", series.title)
    series.description = item.get("description", series.description)
    series.imdbRate = float(item.get("imdbRatingValue", series.imdbRate) or 0)

    series.save()

    if is_created and series.detailPath:
        logger.info(f"[SERIES] New: {series.title}")

        # raw_data = fetch_raw_nuxt_data(
        #     f"https://moviebox.ph/detail/{series.detailPath}?id={series.subjectId}&tab=tv"
        # )

        full_movie_url = f"https://moviebox.ph/detail/{series.detailPath}?id={series.subjectId}&scene=&page_from=type_filter_movie&type=/movie/detail&tab=tv"
        raw_data = fetch_raw_nuxt_data(full_movie_url)

        if raw_data:
            series.trailer = get_trailer_url(raw_data)
            series.description = get_description(raw_data)

            roles = []
            for cast in extract_cast_from_raw(raw_data):
                if not cast.get("staffId") or not cast.get("name"):
                    continue

                actor, _ = Actor.objects.get_or_create(
                    staff_id=cast["staffId"],
                    defaults={"name": cast["name"]}
                )

                role, _ = Role.objects.get_or_create(
                    actor=actor,
                    character=cast.get("character", "")
                )

                roles.append(role)

            series.cast.set(roles)
            series.save()

            save_season_episode_data(series.subjectId, series, raw_data)

    else:
        logger.info(f"[SERIES] Skip: {series.title}")

    return is_created, series

def process_series_item(type, sort="ForYou", page=1, perPage=50):
    created = 0
    updated = 0
    subject_ids = []

    items = [
        i for i in fetch_moviebox_search_results(type, page=page, sort=sort, perPage=perPage)
        if i.get("subjectType") == 2
    ]

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(process_single_series, item) for item in items]

        processed_count = 0

        for future in as_completed(futures):
            try:
                result = future.result()
                if not result:
                    continue

                is_created, series = result

                with lock:
                    subject_ids.append(series.subjectId)
                    created += int(is_created)
                    updated += int(not is_created)

                processed_count += 1
                if processed_count % 10 == 0:
                    logger.info(f"[SERIES] Processed {processed_count}")
                    time.sleep(30)

            except Exception as e:
                logger.exception(f"[SERIES] Error: {e}")

    return {
        "created": created,
        "updated": updated,
        "series": TV_Series.objects.filter(subjectId__in=subject_ids)
    }

def foryou_scrape():
    url = "https://h5-api.aoneroom.com/wefeed-h5api-bff/home?host=moviebox.ph"

    processed_movie_count = 0
    processed_series_count = 0

    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()

        items = response.json().get("data", {}).get("operatingList", [])

        for item in items:
            title = item.get("title")
            type_ = item.get("type")

            logger.info(f"[FORYOU] Processing {title}")
            time.sleep(15)

            foryou_obj, _ = Foryou.objects.get_or_create(title=title)

            movie_list = []
            series_list = []

            def process_movie(subject):
                nonlocal processed_movie_count

                movie, created = Movie.objects.get_or_create(subjectId=subject.get("subjectId"))
                movie_list.append(movie)

                if created:
                    process_single_movie(subject)

                processed_movie_count += 1
                if processed_movie_count % 10 == 0:
                    logger.info("[FORYOU] Movie cooldown")
                    time.sleep(30)

            def process_series(subject):
                nonlocal processed_series_count

                series, created = TV_Series.objects.get_or_create(subjectId=subject.get("subjectId"))
                series_list.append(series)

                if created:
                    process_single_series(subject)

                processed_series_count += 1
                if processed_series_count % 10 == 0:
                    logger.info("[FORYOU] Series cooldown")
                    time.sleep(30)

            subjects = item.get("subjects", [])

            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = []
                for subject in subjects:
                    if subject.get("subjectType") == 1:
                        futures.append(executor.submit(process_movie, subject))
                    elif subject.get("subjectType") == 2:
                        process_series(subject)

                for f in futures:
                    f.result()

            foryou_obj.movie.set(movie_list)
            foryou_obj.tv_series.set(series_list)
            foryou_obj.save()

    except Exception as e:
        logger.exception(f"[FORYOU] Error: {e}")


def process_subject(item):
    subject_type = item.get("subjectType")

    if subject_type == 1:
        return process_single_movie(item)
    elif subject_type == 2:
        return process_single_series(item)

    logger.warning(f"[SKIP] Unknown subjectType={subject_type}")
    return None


def process_moviebox(keyword, limit=10):
    created = 0
    updated = 0

    movie_ids = []
    series_ids = []

    items = search_moviebox_subjects(keyword, limit)

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(process_subject, item) for item in items]

        processed = 0
        for future in as_completed(futures):
            try:
                result = future.result()
                if not result:
                    continue

                is_created, obj = result

                if isinstance(obj, Movie):
                    movie_ids.append(obj.subjectId)
                else:
                    series_ids.append(obj.subjectId)

                created += int(is_created)
                updated += int(not is_created)

                processed += 1
                if processed % 10 == 0:
                    logger.info(f"[PROCESS] {processed}")
                    time.sleep(30)

            except Exception as e:
                logger.exception(f"[PROCESS] Error: {e}")

    return {
        "created": created,
        "updated": updated,
        "movies": Movie.objects.filter(subjectId__in=movie_ids),
        "series": TV_Series.objects.filter(subjectId__in=series_ids),
    }
CACHE_KEY = "everyone_search_data"
CACHE_TIMEOUT = 60 * 60 * 24   # 24 Hours

def scrape_everyone_search():
    try:
        response = requests.get(
            "https://h5-api.aoneroom.com/wefeed-h5api-bff/subject/everyone-search",
            headers=HEADERS,
            timeout=15
        )
        response.raise_for_status()

        data = response.json().get("data", {}).get("everyoneSearch", [])
        cache.set("everyone_search_data", data, timeout=86400)

        return data

    except Exception as e:
        logger.exception(f"[CACHE] Error: {e}")
        return []


def get_year_filter(year_value):
    if not year_value or year_value == "All":
        return {}

    if year_value.endswith("s"):
        decade = int(year_value[:-1])
        return {"releaseDate__year__gte": decade, "releaseDate__year__lt": decade + 10}

    if year_value == "Other":
        return {"releaseDate__year__lt": 1980}

    return {"releaseDate__year": int(year_value)}


