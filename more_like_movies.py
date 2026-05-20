import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "streamflix.settings")
django.setup()

import concurrent.futures
import json
import os
import threading
import time
from datetime import datetime

import django
import requests
from bs4 import BeautifulSoup
from django.db import transaction

from api.services import (
    extract_cast_from_raw,
    fallback_name_from_detail_path,
    fetch_raw_nuxt_data,
    get_description,
    get_trailer_url,
)
from api.models import Actor, Country, Genre, Movie, Role, TV_Series

#
# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "moviebox.settings")
# django.setup()

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


def process_single_movie(item):
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

    movie, is_created = Movie.objects.get_or_create(
        subjectId=subject_id
    )

    movie.title = item.get("title", movie.title)
    movie.description = item.get(
        "description",
        movie.description,
    )
    movie.duration = (
        item.get("duration")
        or movie.duration
    )
    movie.rate = item.get("rate", movie.rate) or 0
    movie.imdbRate = float(
        item.get(
            "imdbRatingValue",
            movie.imdbRate,
        )
        or 0
    )
    movie.subjectType = item.get(
        "subjectType",
        movie.subjectType,
    )
    movie.detailPath = item.get(
        "detailPath",
        movie.detailPath,
    )
    movie.watch_url = item.get(
        "watch_url",
        movie.watch_url,
    )
    movie.corner = item.get(
        "corner",
        movie.corner,
    )
    movie.viewers = item.get(
        "viewers",
        movie.viewers,
    )
    movie.opItemId = item.get(
        "opItemId",
        movie.opItemId,
    )
    movie.seenStatus = item.get(
        "seenStatus",
        movie.seenStatus,
    )
    movie.content = item.get(
        "content",
        movie.content,
    )
    movie.deepLink = item.get(
        "deepLink",
        movie.deepLink,
    )
    movie.cover = item.get(
        "cover",
        movie.cover,
    )
    movie.image = item.get(
        "image",
        movie.image,
    )

    release_date = item.get("releaseDate")

    if release_date:
        try:
            movie.releaseDate = datetime.strptime(
                release_date,
                "%Y-%m-%d",
            ).date()
        except ValueError:
            pass

    ops_data = item.get("ops")
    movie.ops = (
        json.loads(ops_data)
        if isinstance(ops_data, str)
        else ops_data or {}
    )

    subtitles_data = item.get("subtitles")

    if isinstance(subtitles_data, dict):
        movie.subtitles = subtitles_data
    elif isinstance(subtitles_data, str):
        movie.subtitles = {
            "languages": subtitles_data
        }
    else:
        movie.subtitles = {}

    def set_country():
        country_name = item.get("countryName")

        if country_name:
            country_obj, _ = (
                Country.objects.get_or_create(
                    name=country_name.strip()
                )
            )
            movie.country = country_obj

    def set_genres():
        genre_list = []

        genre_string = item.get("genre", "")

        if genre_string:
            for name in [
                genre.strip()
                for genre in genre_string.split(",")
                if genre.strip()
            ]:
                genre_obj, _ = (
                    Genre.objects.get_or_create(
                        name=name
                    )
                )
                genre_list.append(genre_obj)

        movie.genre.set(genre_list)

    def fetch_details():
        if not movie.detailPath:
            return

        full_movie_url = (
            "https://moviebox.ph/detail/"
            f"{movie.detailPath}"
            f"?id={movie.subjectId}"
            "&scene="
            "&page_from=type_filter_movie"
            "&type=/movie/detail"
            "&tab=movie"
        )

        raw_data = fetch_raw_nuxt_data(
            full_movie_url
        )

        if not raw_data:
            return

        trailer_url = get_trailer_url(raw_data)

        if trailer_url:
            movie.trailer = trailer_url

        description = get_description(raw_data)

        if description:
            movie.description = description

        movie_cast_data = extract_cast_from_raw(
            raw_data
        )

        if not movie_cast_data:
            print(
                "[CAST] No cast data found. "
                "Skipping cast processing."
            )
            return

        role_instances = []

        for cast in movie_cast_data:
            staff_id = cast.get("staffId")
            name = cast.get("name")
            character = cast.get("character")
            detail_path = cast.get(
                "detailPath",
                "",
            )

            if (
                not name
                or not name.strip()
            ) and detail_path:
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

            actor, created = (
                Actor.objects.get_or_create(
                    staff_id=staff_id,
                    defaults={
                        "name": name,
                        "image_url": (
                            cast.get(
                                "avatarUrl",
                                "",
                            )
                            or ""
                        ),
                    },
                )
            )

            if (
                not created
                and (
                    not actor.name
                    or not actor.name.strip()
                )
            ):
                actor.name = name
                actor.image_url = (
                    cast.get(
                        "avatarUrl",
                        "",
                    )
                    or ""
                )
                actor.save(
                    update_fields=[
                        "name",
                        "image_url",
                    ]
                )

            role, _ = Role.objects.get_or_create(
                actor=actor,
                character=character or "",
            )

            role_instances.append(role)

        movie.cast.set(role_instances)

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=5
    ) as executor:
        futures = [
            executor.submit(set_country),
            executor.submit(set_genres),
            executor.submit(fetch_details),
        ]
        concurrent.futures.wait(futures)

    movie.save()

    return is_created, movie


def handle_single_movie(movie):
    with lock:
        print(
            "\nProcessing more-like-this "
            f"for Movie: {movie.title} "
            f"({movie.subjectId})"
        )

    recommendations = get_more_like(
        movie.subjectId,
        limit=3,
    )

    if not recommendations:
        with lock:
            print("No movie recommendations found")
        return 0

    linked_count = 0

    for recommendation in recommendations:
        if recommendation.get("subjectType") != 1:
            continue

        try:
            result = process_single_movie(
                recommendation
            )

            if not result:
                continue

            _, more_movie = result

            with transaction.atomic():
                movie.more_like_this.add(
                    more_movie
                )
                movie.save()

            with lock:
                print(
                    f"Linked movie "
                    f"{more_movie.title}"
                )

            linked_count += 1

        except Exception as exc:
            with lock:
                print(
                    "Error processing "
                    f"recommended movie: {exc}"
                )

    return linked_count


def scrape_more_like_movies(
    batch_size=18,
    max_workers=3,
):
    movies = list(
        Movie.objects.filter(
            more_like_this__isnull=True
        )[:batch_size]
    )

    if not movies:
        with lock:
            print("All movies processed!")
        return

    processed_count = 0

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=max_workers
    ) as executor:
        futures = {
            executor.submit(
                handle_single_movie,
                movie,
            ): movie
            for movie in movies
        }

        for future in concurrent.futures.as_completed(
            futures
        ):
            movie = futures[future]

            try:
                future.result()
                processed_count += 1

            except Exception as exc:
                with lock:
                    print(
                        "Error in future for "
                        f"movie {movie.title}: "
                        f"{exc}"
                    )

            if processed_count % 3 == 0:
                with lock:
                    print(
                        "Processed 9 movies, "
                        "sleeping for 30 "
                        "seconds..."
                    )
                time.sleep(30)

    with lock:
        print(
            "Done! Processed "
            f"{processed_count} movies "
            "in this batch."
        )


scrape_more_like_movies()