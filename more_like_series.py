import os
import django


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "streamflix.settings")
django.setup()

import concurrent.futures
import json
import threading
import time
from datetime import datetime

import requests
from django.db import transaction

from api.services import (
    extract_cast_from_raw,
    fallback_name_from_detail_path,
    fetch_raw_nuxt_data,
    get_description,
    get_trailer_url,
    save_season_episode_data,
)
from api.models import Actor, Country, Genre, Role, TV_Series




lock = threading.Lock()


HEADERS = {
    "Host": "h5-api.aoneroom.com",
    "User-Agent": (
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:146.0) "
        "Gecko/20100101 Firefox/146.0"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://moviebox.ph/",
    "Content-Type": "application/json",
    "X-Client-Info": '{"timezone":"Asia/Karachi"}',
    "X-Request-Lang": "en",
    "Origin": "https://moviebox.ph",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site",
    "Authorization": (
        "Bearer "
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJ1aWQiOjM4MTQ0MDU2MzI3Mjg0ODU5MjgsImF0cCI6MywiZXh0Ijoi"
        "MTc2Nzk0MzU0MCIsImV4cCI6MTc3NTcxOTU0MCwiaWF0IjoxNzY3OTQz"
        "MjQwfQ.HTM0CQu1vI7P0btoP1MN3xYPfVD-ALDH_IYSaxhh33c"
    ),
    "Connection": "keep-alive",
}


def get_more_like(subject_id, limit=3):
    """Fetch 'more like this' series."""
    url = (
        "https://h5-api.aoneroom.com/"
        "wefeed-h5api-bff/subject/detail-rec"
    )

    params = {
        "subjectId": subject_id,
        "page": "1",
        "perPage": str(limit),
    }

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            params=params,
            timeout=10,
        )
        response.raise_for_status()

        data = response.json()
        items = data.get("data", {}).get("items", [])

        return items[:limit]

    except Exception as exc:
        print(
            f"Error fetching more_like for "
            f"{subject_id}: {exc}"
        )
        return []


def process_single_series(item):
    subject_id = item.get("subjectId")

    if (
        not subject_id
        or not item.get("title")
        or not item.get("subjectType")
        or not item.get("cover")
    ):
        print(
            f"Skipping subjectId={subject_id} "
            f"due to missing required fields"
        )
        return None

    series, is_created = TV_Series.objects.get_or_create(
        subjectId=subject_id
    )

    series.title = item.get("title", series.title)
    series.description = item.get(
        "description",
        series.description,
    )
    series.duration = (
        item.get("duration")
        or series.duration
    )
    series.rate = item.get("rate", series.rate) or 0
    series.imdbRate = float(
        item.get(
            "imdbRatingValue",
            series.imdbRate,
        )
        or 0
    )
    series.subjectType = item.get(
        "subjectType",
        series.subjectType,
    )
    series.detailPath = item.get(
        "detailPath",
        series.detailPath,
    )
    series.corner = item.get(
        "corner",
        series.corner,
    )
    series.viewers = item.get(
        "viewers",
        series.viewers,
    )
    series.opItemId = item.get(
        "opItemId",
        series.opItemId,
    )
    series.seenStatus = item.get(
        "seenStatus",
        series.seenStatus,
    )
    series.content = item.get(
        "content",
        series.content,
    )
    series.deepLink = item.get(
        "deepLink",
        series.deepLink,
    )
    series.cover = item.get(
        "cover",
        series.cover,
    ) or {}
    series.image = item.get(
        "image",
        series.image,
    ) or {}

    release_date = item.get("releaseDate")

    if release_date:
        try:
            series.releaseDate = datetime.strptime(
                release_date,
                "%Y-%m-%d",
            ).date()
        except ValueError:
            pass

    ops_data = item.get("ops")
    series.ops = (
        json.loads(ops_data)
        if isinstance(ops_data, str)
        else ops_data or {}
    )

    subtitles_data = item.get("subtitles")

    if isinstance(subtitles_data, dict):
        series.subtitles = subtitles_data
    elif isinstance(subtitles_data, str):
        series.subtitles = {
            "languages": subtitles_data
        }
    else:
        series.subtitles = {}

    def set_country():
        country_name = item.get("countryName")

        if country_name:
            country_obj, _ = Country.objects.get_or_create(
                name=country_name.strip()
            )
            series.country = country_obj

    def set_genres():
        genre_list = []

        genre_string = item.get("genre", "")

        if genre_string:
            for name in [
                genre.strip()
                for genre in genre_string.split(",")
                if genre.strip()
            ]:
                genre_obj, _ = Genre.objects.get_or_create(
                    name=name
                )
                genre_list.append(genre_obj)

        series.genre.set(genre_list)

    def fetch_details():
        if not series.detailPath:
            return

        full_url = (
            "https://moviebox.ph/detail/"
            f"{series.detailPath}"
            f"?id={series.subjectId}"
            "&scene="
            "&page_from=type_filter_movie"
            "&type=/movie/detail"
            "&tab=tv"
        )

        raw_data = fetch_raw_nuxt_data(full_url)

        if not raw_data:
            return

        trailer_url = get_trailer_url(raw_data)

        if trailer_url:
            series.trailer = trailer_url

        description = get_description(raw_data)

        if description:
            series.description = description

        cast_data = extract_cast_from_raw(raw_data)

        if not cast_data:
            print(
                "[CAST] No cast data found. "
                "Skipping cast processing "
                "for this series."
            )
        else:
            role_instances = []

            for cast in cast_data:
                staff_id = cast.get("staffId")
                name = cast.get("name")
                character = cast.get("character", "")
                detail_path = cast.get("detailPath", "")

                if (
                    (not name or not name.strip())
                    and detail_path
                ):
                    name = fallback_name_from_detail_path(
                        detail_path
                    )

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
                        "image_url": (
                            cast.get("avatarUrl", "") or ""
                        ),
                    },
                )

                if (
                    not created
                    and (
                        (not actor.name or not actor.name.strip())
                        or not actor.image_url
                    )
                ):
                    actor.name = name
                    actor.image_url = (
                        cast.get("avatarUrl", "") or ""
                    )
                    actor.save(
                        update_fields=[
                            "name",
                            "image_url",
                        ]
                    )

                role, _ = Role.objects.get_or_create(
                    actor=actor,
                    character=character,
                )

                role_instances.append(role)

            series.cast.set(role_instances)

        save_season_episode_data(
            subject_id=series.subjectId,
            series=series,
            raw_data=raw_data,
        )

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=5
    ) as executor:
        futures = [
            executor.submit(set_country),
            executor.submit(set_genres),
            executor.submit(fetch_details),
        ]
        concurrent.futures.wait(futures)

    series.save()

    return is_created, series


def handle_single_series(series):
    with lock:
        print(
            "\nProcessing more-like-this for "
            f"Series: {series.title} "
            f"({series.subjectId})"
        )

    recommendations = get_more_like(
        series.subjectId,
        limit=3,
    )

    if not recommendations:
        with lock:
            print("No series recommendations found")
        return 0

    linked_count = 0

    for recommendation in recommendations:
        if recommendation.get("subjectType") != 2:
            continue

        try:
            result = process_single_series(
                recommendation
            )

            if result:
                _, more_series = result

                with transaction.atomic():
                    series.more_like_this.add(more_series)
                    series.save()

                with lock:
                    print(
                        f"Linked series "
                        f"{more_series.title}"
                    )

                linked_count += 1

        except Exception as exc:
            with lock:
                print(
                    "Error processing "
                    f"recommended series: {exc}"
                )

    return linked_count


def scrape_more_like_series(
    batch_size=18,
    max_workers=3,
):
    series_list = list(
        TV_Series.objects.filter(
            more_like_this__isnull=True
        )[:batch_size]
    )

    if not series_list:
        with lock:
            print("All series processed!")
        return

    processed_count = 0

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=max_workers
    ) as executor:
        futures = {
            executor.submit(
                handle_single_series,
                series,
            ): series
            for series in series_list
        }

        for future in concurrent.futures.as_completed(
            futures
        ):
            series = futures[future]

            try:
                future.result()
                processed_count += 1

            except Exception as exc:
                with lock:
                    print(
                        "Error in future for "
                        f"series {series.title}: "
                        f"{exc}"
                    )

            if processed_count % 3 == 0:
                with lock:
                    print(
                        "Processed 3 series, "
                        "sleeping for 30 seconds..."
                    )
                time.sleep(30)

    with lock:
        print(
            f"Done! Processed "
            f"{processed_count} series "
            f"in this batch."
        )


scrape_more_like_series()