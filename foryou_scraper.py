
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'streamflix.settings')
django.setup()

from django.db import transaction
from datetime import datetime
from api.services import fetch_raw_nuxt_data, get_trailer_url, get_description, extract_cast_from_raw, save_season_episode_data,fallback_name_from_detail_path
from api.models import Movie, Genre, Country, TV_Series, Foryou, Actor, Role
import requests
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from django.utils.dateparse import parse_date
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
    #"Accept-Encoding": "gzip, deflate, br, zstd",
    "Content-Type": "application/json",
    #"Content-Length": "123",
    "Referer": "https://moviebox.ph/",
    "X-Client-Info": '{"timezone":"Asia/Karachi"}',
    "X-Request-Lang": "en",
    "Origin": "https://moviebox.ph",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site",
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1aWQiOjM4MTQ0MDU2MzI3Mjg0ODU5MjgsImF0cCI6MywiZXh0IjoiMTc2Nzk0MzU0MCIsImV4cCI6MTc3NTcxOTU0MCwiaWF0IjoxNzY3OTQzMjQwfQ.HTM0CQu1vI7P0btoP1MN3xYPfVD-ALDH_IYSaxhh33c",
    "Connection": "keep-alive",
    "Priority": "u=4",
    "TE": "trailers"
}
# def fetch_moviebox_search_results(type, sort="ForYou", page=1, perPage=30):
#     # url = 'https://moviebox.ph/wefeed-h5-bff/web/filter'
#     url = "https://h5-api.aoneroom.com/wefeed-h5api-bff/subject/filter"
#     payload = {
#         "page":page,
#         "perPage":perPage,
#         "channelId": 1 if type=='movies' else 2,
#         "year":"All",
#         "sort":sort
#     }
#     response = requests.post(url, headers=HEADERS, json=payload)
#     print(response.json())
#     response.raise_for_status()
#     return response.json().get("data", {}).get("items", [])

def fetch_moviebox_search_results(type, sort="ForYou", page=1, perPage=30):
    url = "https://h5-api.aoneroom.com/wefeed-h5api-bff/subject/filter"

    payload = {
        "page": page,
        "perPage": perPage,
        "channelId": 1 if type=='movies' else 2,
        "genre": "All",
        "country": "United States",
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

    print("\n🔍 SUBJECT FILTER DEBUG")
    print("Status:", response.status_code)
    print("URL:", response.url)
    print("Body preview:", response.text[:500])

    response.raise_for_status()

    if not response.text.strip():
        raise RuntimeError("❌ Empty response body")

    data = response.json()
    print("✅ JSON parsed successfully")
    return data.get("data", {}).get("items", [])


#For movies..........
@transaction.atomic
def process_single_movie(item):
    subject_id = item.get("subjectId")
    if not subject_id or not item.get("title") or not item.get("subjectType") or not item.get("cover"):
        print(f"⚠️ Skipping subjectId={subject_id} due to missing required fields")
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
            pass

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
        #full_movie_url = f"https://moviebox.ph/detail/{movie.detailPath}?id={movie.subjectId}&scene=&page_from=type_filter_movie&type=/movie/detail&utm_source=&tab=movie"
        full_movie_url = f"https://moviebox.ph/detail/{movie.detailPath}?id={movie.subjectId}&scene=&page_from=type_filter_movie&type=/movie/detail&tab=movie"
        raw_data = fetch_raw_nuxt_data(full_movie_url)
        if raw_data:
            trailer_url = get_trailer_url(raw_data)
            if trailer_url:
                movie.trailer = trailer_url

            description = get_description(raw_data)
            if description:
                movie.description = description

            movie_cast_data = extract_cast_from_raw(raw_data)

            # Skip processing if no cast data found
            if not movie_cast_data:
                print("[CAST] No cast data found. Skipping cast processing for this movie.")
            else:
                role_instances = []

                for cast in movie_cast_data:
                    staff_id = cast.get("staffId")
                    name = cast.get("name")
                    character = cast.get("character")
                    detail_path = cast.get("detailPath", "")

                    # Fallback to detailPath if name missing or empty
                    if not name or not name.strip():
                        if detail_path:
                            name = fallback_name_from_detail_path(detail_path)
                            print(f"[DB] ℹ️ Fallback resolved name '{name}' from detailPath '{detail_path}'")

                    # Validate staff_id and name presence and non-empty after strip
                    if not staff_id or not str(staff_id).strip() or not name or not name.strip():
                        print(f"[DB] ⚠️ Skipping cast entry (missing or empty staffId or name): {cast}")
                        continue

                    name = name.strip()

                    actor, created = Actor.objects.get_or_create(
                        staff_id=staff_id,
                        defaults={
                            "name": name,
                            "image_url": cast.get("avatarUrl", "") or ""
                        }
                    )

                    # Backfill name and image_url if actor existed but missing name
                    if not created and (not actor.name or not actor.name.strip()):
                        actor.name = name
                        actor.image_url = cast.get("avatarUrl", "") or ""
                        actor.save(update_fields=["name", "image_url"])

                    role, _ = Role.objects.get_or_create(
                        actor=actor,
                        character=character or ""
                    )

                    role_instances.append(role)

                # Assign all role instances to movie's cast relation
                movie.cast.set(role_instances)

                movie.save()

    return is_created, movie

@transaction.atomic
def process_single_series(item):
    subject_id = item.get("subjectId")
    if not subject_id or not item.get("title") or not item.get("subjectType") or not item.get("cover"):
        print(f"⚠️ Skipping subjectId={subject_id} due to missing required fields")
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
            series.releaseDate = datetime.strptime(release_date, "%Y-%m-%d").date()
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
        country_obj, _ = Country.objects.get_or_create(name=country_name.strip())
        series.country = country_obj
    else:
        series.country = None

    series.save()

    # ✅ Handle genres (ManyToMany)
    genre_list = []
    genre_string = item.get("genre", "")
    if genre_string:
        for name in [g.strip() for g in genre_string.split(',') if g.strip()]:
            genre_obj, _ = Genre.objects.get_or_create(name=name)
            genre_list.append(genre_obj)
    series.genre.set(genre_list)
    series.save()

    # ✅ Fetch and assign cast if detailPath exists
    if series.detailPath:
        #full_movie_url = f"https://moviebox.ph/detail/{series.detailPath}?id={series.subjectId}&scene=&page_from=type_filter_tv&type=/movie/detail&utm_source=&tab=tv"
        full_movie_url = f"https://moviebox.ph/detail/{series.detailPath}?id={series.subjectId}&scene=&page_from=type_filter_movie&type=/movie/detail&tab=tv"
        raw_data = fetch_raw_nuxt_data(full_movie_url)
        if raw_data:
            trailer_url = get_trailer_url(raw_data)
            if trailer_url:
                series.trailer = trailer_url

            description = get_description(raw_data)
            if description:
                series.description = description

            # ✅ Extract cast
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
                            print(f"[DB] ℹ️ Fallback resolved name '{name}' from detailPath '{detail_path}'")

                    # Validate staff_id and name presence and non-empty after strip
                    if not staff_id or not str(staff_id).strip() or not name or not name.strip():
                        print(f"[DB] ⚠️ Skipping cast entry (missing or empty staffId or name): {cast}")
                        continue

                    name = name.strip()

                    actor, created = Actor.objects.get_or_create(
                        staff_id=staff_id,
                        defaults={
                            "name": name,
                            "image_url": cast.get("avatarUrl", "") or ""
                        }
                    )

                    # Backfill name and image_url if actor existed but missing name or image
                    if not created and ((not actor.name or not actor.name.strip()) or (not actor.image_url)):
                        actor.name = name
                        actor.image_url = cast.get("avatarUrl", "") or ""
                        actor.save(update_fields=["name", "image_url"])

                    role, _ = Role.objects.get_or_create(
                        actor=actor,
                        character=character
                    )

                    role_instances.append(role)

                series.cast.set(role_instances)

                # ✅ Save updates
                series.save()

                save_season_episode_data(subject_id=series.subjectId, series=series, raw_data=raw_data)

            return is_created, series




def create_movie_quick(subject):
    with lock:
        movie, created = Movie.objects.get_or_create(
            subjectId=subject["subjectId"],
            defaults={
                "title": subject.get("title", ""),
                "cover": subject.get("cover", {}),
                "rate": subject.get("rate", 0.0),
                "imdbRate": subject.get("imdbRate", 0.0),
                "releaseDate": parse_date(subject.get("releaseDate")),
                "detailPath": subject.get("detailPath"),
            }
        )
    return movie, created

def create_series_quick(subject):
    with lock:
        series, created = TV_Series.objects.get_or_create(
            subjectId=subject["subjectId"],
            defaults={
                "title": subject.get("title", ""),
                "cover": subject.get("cover", {}),
                "rate": subject.get("rate", 0.0),
                "imdbRate": subject.get("imdbRate", 0.0),
                "releaseDate": parse_date(subject.get("releaseDate")),
                "detailPath": subject.get("detailPath"),
            }
        )
    return series, created


def fetch_movie_details_thread(subject):
    try:
        process_single_movie(subject)  # Uses full detail logic
        #print(f"✅ Movie details updated: {subject.get('title')}")
    except Exception:
        pass
        #print(f"❌ Failed to fetch movie details {subject.get('title')}: {e}")

def fetch_series_details_thread(subject):
    try:
        process_single_series(subject)  # Uses full detail logic
        #print(f"✅ Series details updated: {subject.get('title')}")
    except Exception:
        pass
        #print(f"❌ Failed to fetch series details {subject.get('title')}: {e}")


def process_subject_thread(subject, movie_list, series_list):
    try:
        if subject.get("subjectType") == 1:  # Movie
            movie, created = create_movie_quick(subject)
            movie_list.append(movie)
            if created:
                process_single_movie(subject)

        elif subject.get("subjectType") == 2:  # Series
            series, created = create_series_quick(subject)
            series_list.append(series)
            if created:
                process_single_series(subject)
    except Exception:
            pass
        #print(f"❌ Error processing subject {subject.get('title')}: {e}")


# def foryou_scrape():
#     # url = "https://moviebox.ph/wefeed-h5-bff/web/home"
#     url = "https://h5-api.aoneroom.com/wefeed-h5api-bff/home?host=moviebox.ph"
#     # headers = {
#     #     "User-Agent": "Mozilla/5.0",
#     #     "Accept": "application/json",
#     # }
#     headers = {
#         "Accept": "application/json",
#         #"Accept-Encoding": "gzip, deflate, br, zstd",
#         "Accept-Language": "en-US,en;q=0.5",
#         "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1aWQiOjM4MTQ0MDU2MzI3Mjg0ODU5MjgsImF0cCI6MywiZXh0IjoiMTc2Nzk0MzU0MCIsImV4cCI6MTc3NTcxOTU0MCwiaWF0IjoxNzY3OTQzMjQwfQ.HTM0CQu1vI7P0btoP1MN3xYPfVD-ALDH_IYSaxhh33c",
#         "Connection": "keep-alive",
#         "Content-Type": "application/json",
#         "Host": "h5-api.aoneroom.com",
#         "Origin": "https://moviebox.ph",
#         "Referer": "https://moviebox.ph/",
#         "Sec-Fetch-Dest": "empty",
#         "Sec-Fetch-Mode": "cors",
#         "Sec-Fetch-Site": "cross-site",
#         "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:146.0) Gecko/20100101 Firefox/146.0",
#         "X-Client-Info": '{"timezone":"Asia/Karachi"}',
#         "X-Request-Lang": "en"
#     }
#
#     try:
#         response = requests.get(url, headers=headers, timeout=15)
#         response.raise_for_status()
#         data = response.json()
#         print("✅ Got JSON response")
#
#         items = data.get("data", {}).get("operatingList", [])
#
#         allowed_types = {"BANNER", "SUBJECTS_MOVIE", "APPOINTMENT_LIST"}
#
#         for index, item in enumerate(items):
#             title = item.get("title")
#             type_ = item.get("type")
#
#             if type_ not in allowed_types:
#                 continue
#             print(f"\n🔹 Processing Foryou section: {title} ({type_})")
#
#             # foryou_obj, _ = Foryou.objects.get_or_create(title=title)
#             foryou_obj = Foryou.objects.filter(title=title).first()
#             if not foryou_obj:
#                 foryou_obj = Foryou.objects.create(title=title)
#
#             movie_list = []
#             series_list = []
#
#             # Collect subjects
#             subjects = []
#             if type_ == "BANNER":
#                 banners = item.get("banner", {}).get("items", [])
#                 for banner in banners:
#                     if banner.get("subject"):
#                         subjects.append(banner["subject"])
#             elif type_ in ["SUBJECTS_MOVIE", "APPOINTMENT_LIST"]:
#                 raw_subjects = item.get("subjects")
#                 if isinstance(raw_subjects, list):
#                     subjects = [s for s in raw_subjects if s.get("subjectId")]
#
#             # Threaded execution for all subjects
#             with ThreadPoolExecutor(max_workers=6) as executor:
#                 futures = [executor.submit(process_subject_thread, subject, movie_list, series_list)
#                            for subject in subjects]
#
#                 for i, _ in enumerate(futures, start=1):
#                     if i % 10 == 0:
#                         print("⏳ Pausing 30 seconds after 10 processed subjects...")
#                         time.sleep(30)
#
#             # Save to DB
#             with lock:
#                 foryou_obj.movie.set(movie_list)
#                 foryou_obj.tv_series.set(series_list)
#                 foryou_obj.save()
#                 print(f"📝 Saved Foryou '{title}' with {len(movie_list)} movies and {len(series_list)} series.")
#
#             print(f"⏳ Pausing 15 seconds after section '{title}'...")
#             time.sleep(15)
#
#         print("All Foryou sections processed.")
#
#     except Exception as e:
#         #pass
#         print("Error fetching data:", e)


def foryou_scrape():
    url = "https://h5-api.aoneroom.com/wefeed-h5api-bff/home?host=moviebox.ph"

    headers = {
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.5",
        "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1aWQiOjM4MTQ0MDU2MzI3Mjg0ODU5MjgsImF0cCI6MywiZXh0IjoiMTc2Nzk0MzU0MCIsImV4cCI6MTc3NTcxOTU0MCwiaWF0IjoxNzY3OTQzMjQwfQ.HTM0CQu1vI7P0btoP1MN3xYPfVD-ALDH_IYSaxhh33c",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "Host": "h5-api.aoneroom.com",
        "Origin": "https://moviebox.ph",
        "Referer": "https://moviebox.ph/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "cross-site",
        "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:146.0) Gecko/20100101 Firefox/146.0",
        "X-Client-Info": '{"timezone":"Asia/Karachi"}',
        "X-Request-Lang": "en",
    }

    processed_movie_count = 0
    processed_series_count = 0

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        items = response.json().get("data", {}).get("operatingList", [])

        allowed_types = {"BANNER", "SUBJECTS_MOVIE", "APPOINTMENT_LIST"}

        for item in items:
            title = item.get("title")
            type_ = item.get("type")

            if type_ not in allowed_types:
                continue

            print(f"\n🔹 Processing Foryou section: {title} ({type_})")
            time.sleep(15)

            foryou_obj, _ = Foryou.objects.get_or_create(title=title)
            movie_list, series_list = [], []

            # ------------------------------
            # Collect subjects
            # ------------------------------
            subjects = []

            if type_ == "BANNER":
                for banner in item.get("banner", {}).get("items", []):
                    if banner.get("subject"):
                        subjects.append(banner["subject"])

            else:
                raw_subjects = item.get("subjects", [])
                if isinstance(raw_subjects, list):
                    subjects = [s for s in raw_subjects if s.get("subjectId")]

            # ------------------------------
            # Processing logic
            # ------------------------------
            def process_movie(subject):
                nonlocal processed_movie_count

                with lock:
                    movie, created = Movie.objects.get_or_create(
                        subjectId=subject["subjectId"],
                        defaults={
                            "title": subject.get("title"),
                            "cover": subject.get("cover", {}).get("url"),
                            "rate": subject.get("rate") or 0.0,
                            "imdbRate": subject.get("imdbRate") or 0.0,
                            "releaseDate": parse_date(subject.get("releaseDate")),
                            "detailPath": subject.get("detailPath"),
                        }
                    )
                    movie_list.append(movie)

                # if created:
                #     try:
                #         process_single_movie(subject)
                #         print(f"🎯 Movie details fetched: {movie.title}")
                #     except Exception as e:
                #         print(f"❌ Movie detail error: {movie.title} → {e}")

                if created:
                    print(f"🎯 New movie created: {movie.title} — fetching full details...")
                    try:
                        process_single_movie(subject)
                        print(f"✅ Details fetched for movie: {movie.title}")
                    except Exception as e:
                        print(f"❌ Failed to fetch movie details for {movie.title}: {e}")
                else:
                    print(f"♻️ Movie already exists: {movie.title} — skipping detail fetch")

                processed_movie_count += 1
                if processed_movie_count % 10 == 0:
                    print("⏳ 10 movies processed — sleeping 30s")
                    time.sleep(30)

            def process_series(subject):
                nonlocal processed_series_count

                with lock:
                    series, created = TV_Series.objects.get_or_create(
                        subjectId=subject["subjectId"],
                        defaults={
                            "title": subject.get("title"),
                            "cover": subject.get("cover", {}).get("url"),
                            "rate": subject.get("rate") or 0.0,
                            "imdbRate": subject.get("imdbRate") or 0.0,
                            "releaseDate": parse_date(subject.get("releaseDate")),
                            "detailPath": subject.get("detailPath"),
                        }
                    )
                    series_list.append(series)

                # if created:
                #     try:
                #         process_single_series(subject)
                #         print(f"🎯 Series details fetched: {series.title}")
                #     except Exception as e:
                #         print(f"❌ Series detail error: {series.title} → {e}")

                if created:
                    print(f"🎯 New series created: {series.title} — fetching full details...")
                    try:
                        process_single_series(subject)
                        print(f"✅ Details fetched for series: {series.title}")
                    except Exception as e:
                        print(f"❌ Failed to fetch series details for {series.title}: {e}")
                else:
                    print(f"♻️ Series already exists: {series.title} — skipping detail fetch")

                processed_series_count += 1
                if processed_series_count % 10 == 0:
                    print("⏳ 10 series processed — sleeping 30s")
                    time.sleep(30)

            # ------------------------------
            # Hybrid concurrency
            # ------------------------------
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = []

                for subject in subjects:
                    if subject.get("subjectType") == 1:  # Movie
                        futures.append(executor.submit(process_movie, subject))
                    elif subject.get("subjectType") == 2:  # Series
                        process_series(subject)  # sequential

                for future in futures:
                    future.result()

            # ------------------------------
            # Save relations
            # ------------------------------
            with lock:
                foryou_obj.movie.set(movie_list)
                foryou_obj.tv_series.set(series_list)
                foryou_obj.save()

            print(
                f"📝 Saved '{title}' → "
                f"{len(movie_list)} movies, {len(series_list)} series"
            )

        print("\n✅ All Foryou sections processed successfully.")

    except Exception as e:
        print("❌ Error during Foryou scrape:", e)


# Run the scraperS
foryou_scrape()