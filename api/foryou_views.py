from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

from django.core.cache import cache
from django.db.models import Q
import random
import requests

from .models import Foryou
from .serializers import (
    ForyouSerializer,
    ForyouMoviesSerializer,
    ForyouSeriesSerializer,
    MovieDetailSerializer,
    TVSeriesDetailSerializer,
    MovieSerializer,
    TVSeriesSerializer,
)
from .services import scrape_everyone_search, foryou_scrape
from .pagination import CustomPagination
from .utils import generate_cache_key, get_cached_response, set_cached_response


# ==========================================
# RESPONSE WRAPPER (PRODUCTION STANDARD)
# ==========================================
class APIResponse:

    @staticmethod
    def success(data=None, message="Success", status_code=status.HTTP_200_OK):
        return Response({
            "success": True,
            "message": message,
            "data": data,
            "errors": None
        }, status=status_code)

    @staticmethod
    def error(message="Error", errors=None, status_code=status.HTTP_400_BAD_REQUEST):
        return Response({
            "success": False,
            "message": message,
            "data": None,
            "errors": errors
        }, status=status_code)


# ==========================================
# EVERYONE SEARCH
# ==========================================
class EveryoneSearchView(APIView):

    def get(self, request):
        try:
            cached_data = cache.get("everyone_search")

            if cached_data:
                return APIResponse.success(data=cached_data)

            data = scrape_everyone_search()

            return APIResponse.success(data=data)

        except requests.RequestException as e:
            return APIResponse.error(
                message="External service error",
                errors=str(e),
                status_code=status.HTTP_502_BAD_GATEWAY
            )

        except Exception as e:
            return APIResponse.error(
                message="Internal server error",
                errors=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ==========================================
# FORYOU ALL
# ==========================================
class ForyouAll(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cache_key = generate_cache_key("foryou:all", request)
        cached_res = get_cached_response(cache_key)
        if cached_res:
            return cached_res

        size = request.query_params.get("size", 3)
        subject_type = request.query_params.get("type")

        try:
            size = int(size)
        except:
            size = 3

        queryset = (
            Foryou.objects
            .filter(is_active=True)
            .order_by("order_by")
            .distinct()
        )

        queryset = queryset.prefetch_related(
            "movie",
            "tv_series",
            "movie__genre",
            "tv_series__genre",
            "movie__country",
            "tv_series__country",
        )

        if subject_type == "movies":
            queryset = queryset.filter(movie__isnull=False).distinct()
            serializer_class = ForyouMoviesSerializer

        elif subject_type == "series":
            queryset = queryset.filter(tv_series__isnull=False).distinct()
            serializer_class = ForyouSeriesSerializer

        else:
            serializer_class = ForyouSerializer

        serializer = serializer_class(
            queryset,
            many=True,
            context={"paginate": True, "value_of_splice": size}
        )

        filtered = [i for i in serializer.data if i.get("data")]

        response = APIResponse.success(data=filtered)
        set_cached_response(cache_key, response.data)
        return response


# ==========================================
# FORYOU BY ID
# ==========================================
class ForyouById(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        obj_id = request.query_params.get("id")
        subject_type = request.query_params.get("type")

        if not obj_id:
            return APIResponse.error(message="id is required")

        cache_key = generate_cache_key("foryou:id", request)
        cached_res = get_cached_response(cache_key)
        if cached_res:
            return cached_res

        obj = Foryou.objects.filter(id=obj_id, is_active=True).first()

        if not obj:
            return APIResponse.error(
                message="Not found",
                status_code=status.HTTP_404_NOT_FOUND
            )

        if subject_type == "movies":
            serializer = ForyouMoviesSerializer(obj, context={"paginate": False})
        elif subject_type == "series":
            serializer = ForyouSeriesSerializer(obj, context={"paginate": False})
        else:
            serializer = ForyouSerializer(obj, context={"paginate": False})

        response = APIResponse.success(data=serializer.data)
        set_cached_response(cache_key, response.data)
        return response


# ==========================================
# FORYOU MOVIES
# ==========================================
class ForyouMoviesAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cache_key = generate_cache_key("foryou:movies", request)
        cached_res = get_cached_response(cache_key)
        if cached_res:
            return cached_res

        limit = int(request.query_params.get("limit", 3))

        queryset = (
            Foryou.objects
            .filter(movie__isnull=False)
            .order_by("order_by")
            .distinct()
        )

        serializer = ForyouMoviesSerializer(
            queryset,
            many=True,
            context={"paginate": True, "value_of_splice": limit}
        )

        response = APIResponse.success(data=serializer.data)
        set_cached_response(cache_key, response.data)
        return response


# ==========================================
# FORYOU SERIES
# ==========================================
class ForyouSeriesAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cache_key = generate_cache_key("foryou:series", request)
        cached_res = get_cached_response(cache_key)
        if cached_res:
            return cached_res

        limit = int(request.query_params.get("limit", 5))

        queryset = (
            Foryou.objects
            .filter(tv_series__isnull=False)
            .order_by("order_by")
            .distinct()
        )

        paginator = CustomPagination()
        page = paginator.paginate_queryset(queryset, request)

        serializer = ForyouSeriesSerializer(
            page,
            many=True,
            context={"paginate": True, "value_of_splice": limit}
        )

        response = paginator.get_paginated_response(serializer.data)
        set_cached_response(cache_key, response.data)
        return response


# ==========================================
# FORYOU SCRAPE
# ==========================================
class ForyouScrapeView(APIView):

    def get(self, request):
        try:
            foryou_scrape()

            queryset = Foryou.objects.all().distinct()
            serializer = ForyouSerializer(queryset, many=True)

            cache.clear()

            return APIResponse.success(
                data=serializer.data,
                message="Foryou synced successfully"
            )

        except Exception as e:
            return APIResponse.error(
                message="Scraping failed",
                errors=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ==========================================
# TRENDING PAGE
# ==========================================
class TrendingPageAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        page = request.GET.get("page", "Trending Now")
        limit = int(request.GET.get("limit", 30))

        cache_key = f"trending_{page}_{limit}"
        cached = cache.get(cache_key)

        if cached:
            return APIResponse.success(data=cached)

        queryset = (
            Foryou.objects
            .filter(is_active=True)
            .order_by("order_by")
            .distinct()
        )

        if page == "Trending Now":
            sections = []

            for item in queryset:
                movies = item.movie.all().distinct()[:limit]
                series = item.tv_series.all().distinct()[:limit]

                if movies:
                    data = MovieDetailSerializer(movies, many=True).data
                else:
                    data = TVSeriesDetailSerializer(series, many=True).data

                sections.append({
                    "title": item.title,
                    "items": data
                })

            response_data = {
                "status": True,
                "page": page,
                "sections": sections
            }

        else:
            item = queryset.filter(title=page).first()

            if not item:
                return APIResponse.error(
                    message="Page not found",
                    status_code=status.HTTP_404_NOT_FOUND
                )

            movies = item.movie.all().distinct()[:limit]
            series = item.tv_series.all().distinct()[:limit]

            data = []

            if movies:
                data.extend(MovieDetailSerializer(movies, many=True).data)

            if series:
                remain = limit - len(data)
                data.extend(TVSeriesDetailSerializer(series[:remain], many=True).data)

            response_data = {
                "status": True,
                "data": {
                    "title": page,
                    "section": data
                }
            }

        cache.set(cache_key, response_data, 1800)
        return APIResponse.success(data=response_data)


# ==========================================
# FORYOU COMBINED
# ==========================================
class ForyouCombinedAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cache_key = generate_cache_key("foryou:combined", request)
        cached_res = get_cached_response(cache_key)
        if cached_res:
            return cached_res

        movies = []
        series = []

        genre_param = request.GET.get("genre", "")
        selected_genres = [g.strip() for g in genre_param.split(",") if g.strip()]

        movies_limit = int(request.GET.get("movies", 100))
        series_limit = int(request.GET.get("series", 100))

        for item in Foryou.objects.prefetch_related(
            "movie__genre",
            "tv_series__genre"
        ).all().distinct():

            movie_queryset = item.movie.all().distinct()
            series_queryset = item.tv_series.all().distinct()

            if selected_genres:
                movie_query = Q()
                series_query = Q()

                for genre in selected_genres:
                    movie_query |= Q(genre__name__iexact=genre)
                    series_query |= Q(genre__name__iexact=genre)

                movie_queryset = movie_queryset.filter(movie_query).distinct()
                series_queryset = series_queryset.filter(series_query).distinct()

            movies.extend(MovieSerializer(movie_queryset, many=True).data)
            series.extend(TVSeriesSerializer(series_queryset, many=True).data)

        random.shuffle(movies)
        random.shuffle(series)

        response = APIResponse.success(data={
            "movies": movies[:movies_limit],
            "series": series[:series_limit]
        })
        set_cached_response(cache_key, response.data)
        return response