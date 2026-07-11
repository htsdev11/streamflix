import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'streamflix.settings')
django.setup()

import requests
import json
from datetime import datetime
from django.db import transaction
from api.models import Movie, Genre, Country, TV_Series, Foryou, Actor, Role
from api.services import (
    fetch_raw_nuxt_data,
    get_trailer_url,
    get_description,
    extract_cast_from_raw,
    process_single_series,
    save_season_episode_data,
    fallback_name_from_detail_path
)
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

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
    # "Accept-Encoding": "gzip, deflate, br, zstd",
    "Content-Type": "application/json",
    # "Content-Length": "123",
    "Referer": "https://moviebox.ph/",
    "X-Client-Info": '{"timezone":"Asia/Karachi"}',
    "X-Request-Lang": "en",
    "Origin": "https://moviebox.ph",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site",
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1aWQiOjQ1NjI1MjIwNzU5MzU3ODUzOTIsImF0cCI6MywiZXh0IjoiMTc3ODAwMzE3OCIsImV4cCI6MTc4NTc3OTE3OCwiaWF0IjoxNzc4MDAyODc4fQ.-zojTZf3ZOsX7tdMJWrtACPRC-BkByUm8vgZ5vKmKx0",
    "Connection": "keep-alive",
    "Priority": "u=4",
    "TE": "trailers"
}


# def fetch_moviebox_search_results(type, sort="ForYou", page=1, perPage=50):
#     url = 'https://moviebox.ph/wefeed-h5-bff/web/filter'
#
#     payload = {
#         "page",
#         "perPage",
#         "channelId": 1 if type == 'movies' else 2,
#         "year": "All",
#         "sort"
#     }
#
#     response = requests.post(url, headers=HEADERS, json=payload)
#
#     # print(response.json())
#
#     response.raise_for_status()
#
#     return response.json().get("data", {}).get("items", [])


def fetch_moviebox_search_results(type, sort="ForYou", page=1, perPage=30):
    url = "https://h5-api.aoneroom.com/wefeed-h5api-bff/subject/filter"

    # payload = {
    #     "page": page,
    #     "perPage": perPage,
    #     "channelId": 1 if type == "movies" else 2,
    #     "year": "All",
    #     "sort": sort
    # }

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

    response = requests.post(
        url,
        headers=HEADERS,
        json=payload,
        timeout=15
    )

    print("\n? SUBJECT FILTER DEBUG")
    print("Status:", response.status_code)
    print("URL:", response.url)
    print("Body preview:", response.text[:500])

    response.raise_for_status()

    if not response.text.strip():
        raise RuntimeError("? Empty response body")

    data = response.json()
    print("? JSON parsed successfully")

    return data.get("data", {}).get("items", [])


@transaction.atomic
def process_single_series(item):
    subject_id = item.get("subjectId")

    if (
        not subject_id
        or not item.get("title")
        or not item.get("subjectType")
        or not item.get("cover")
    ):
        print(f"?? Skipping subjectId={subject_id} due to missing required fields")
        return None

    series, is_created = TV_Series.objects.get_or_create(subjectId=subject_id)

    series.title = item.get("title", series.title)
    series.description = item.get("description", series.description)
    series.duration = item.get("duration") or series.duration
    series.rate = item.get("rate", series.rate) or 0
    series.imdbRate = float(item.get("imdbRatingValue", series.imdbRate) or 0)
    series.subjectType = item.get("subjectType", series.subjectType)

    release_date = item.get("releaseDate")

    if release_date:
        try:
            series.releaseDate = datetime.strptime(
                release_date, "%Y-%m-%d"
            ).date()
        except ValueError:
            pass

    series.detailPath = item.get("detailPath", series.detailPath)

    ops_data = item.get("ops")

    if isinstance(ops_data, str):
        try:
            series.ops = json.loads(ops_data)
        except json.JSONDecodeError:
            series.ops = {}
    else:
        series.ops = ops_data or {}

    subtitles_data = item.get("subtitles")

    if isinstance(subtitles_data, dict):
        series.subtitles = subtitles_data
    elif isinstance(subtitles_data, str):
        series.subtitles = {"languages": subtitles_data}
    else:
        series.subtitles = {}

    series.corner = item.get("corner", series.corner)
    series.viewers = item.get("viewers", series.viewers)
    series.opItemId = item.get("opItemId", series.opItemId)
    series.seenStatus = item.get("seenStatus", series.seenStatus)
    series.content = item.get("content", series.content)
    series.deepLink = item.get("deepLink", series.deepLink)
    series.cover = item.get("cover", series.cover) or {}
    series.image = item.get("image", series.image) or {}

    country_name = item.get("countryName")

    if country_name:
        country_obj, _ = Country.objects.get_or_create(
            name=country_name.strip()
        )
        series.country = country_obj
    else:
        series.country = None

    series.save()

    # ? Handle genres (ManyToMany)
    genre_list = []
    genre_string = item.get("genre", "")

    if genre_string:
        for name in [g.strip() for g in genre_string.split(',') if g.strip()]:
            genre_obj, _ = Genre.objects.get_or_create(name=name)
            genre_list.append(genre_obj)

    series.genre.set(genre_list)
    series.save()

    # ? Fetch and assign cast if detailPath exists
    if series.detailPath:
        full_movie_url = f"https://moviebox.ph/detail/{series.detailPath}?id={series.subjectId}&scene=&page_from=type_filter_movie&type=/movie/detail&tab=tv"

        # full_movie_url = (
        #     f"https://moviebox.ph/detail/{series.detailPath}"
        #     f"?id={series.subjectId}"
        #     f"&scene=&page_from=type_filter_movie"
        #     f"&type=/movie/detail&tab=tv"
        # )

        raw_data = fetch_raw_nuxt_data(full_movie_url)

        if raw_data:
            trailer_url = get_trailer_url(raw_data)

            if trailer_url:
                series.trailer = trailer_url

            description = get_description(raw_data)

            if description:
                series.description = description

            # ? Extract cast
            movie_cast_data = extract_cast_from_raw(raw_data)

            # Skip processing if no cast data found
            if not movie_cast_data:
                print("[CAST] No cast data found. Skipping cast processing for this series.")

            else:
                role_instances = []

                for cast in movie_cast_data:
                    staff_id = cast.get("staffId")
                    name = cast.get("name")
                    character = cast.get("character", "")
                    detail_path = cast.get("detailPath", "")

                    # Fallback to detailPath if name missing or empty
                    if not name or not name.strip():
                        if detail_path:
                            name = fallback_name_from_detail_path(detail_path)

                    # Validate staff_id and name presence
                    if (
                        not staff_id
                        or not str(staff_id).strip()
                        or not name
                        or not name.strip()
                    ):
                        continue

                    name = name.strip()

                    actor, created = Actor.objects.get_or_create(
                        staff_id=staff_id,
                        defaults={
                            "name": name,
                            "image_url": cast.get("avatarUrl", "") or ""
                        }
                    )

                    # Backfill if actor exists but missing fields
                    if not created and (
                        (not actor.name or not actor.name.strip())
                        or (not actor.image_url)
                    ):
                        actor.name = name
                        actor.image_url = cast.get("avatarUrl", "") or ""
                        actor.save(update_fields=["name", "image_url"])

                    role, _ = Role.objects.get_or_create(
                        actor=actor,
                        character=character
                    )

                    role_instances.append(role)

                series.cast.set(role_instances)

                # ? Save updates
                series.save()

                save_season_episode_data(
                    subject_id=series.subjectId,
                    series=series,
                    raw_data=raw_data
                )

            return is_created, series


def process_series_item(type, sort="ForYou", page=1, perPage=50):
    created = 0
    updated = 0
    subject_ids = []

    items = [
        i for i in fetch_moviebox_search_results(
            type,
            page=page,
            sort=sort,
            perPage=perPage
        )
        if i.get("subjectType") == 2
    ]

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(process_single_series, item)
            for item in items
        ]

        processed_count = 0

        for future in as_completed(futures):
            try:
                result = future.result()

                if not result:
                    continue

                is_created, series = result

                with lock:
                    subject_ids.append(series.subjectId)

                    if is_created:
                        created += 1
                    else:
                        updated += 1

                processed_count += 1

                if processed_count % 10 == 0:
                    print(
                        f"Processed {processed_count} items. "
                        f"Sleeping for 30 seconds..."
                    )
                    time.sleep(30)

            except Exception as e:
                print(f"Error processing series: {e}")

    return {
        "created": created,
        "updated": updated,
        "series": TV_Series.objects.filter(subjectId__in=subject_ids)
    }


process_series_item("series")
