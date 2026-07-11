from django.db.models import Q
from django.core.cache import cache

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

from .models import TV_Series, Genre, SearchLog
from .serializers import (
    TVSeriesSerializer,
    TVSeriesDetailSerializer
)
from .pagination import CustomPagination
from .services import process_series_item, get_year_filter
from .utils import generate_cache_key, get_cached_response, set_cached_response


# ==========================================
# RESPONSE WRAPPER (STANDARD)
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
# SERIES SEARCH
# ==========================================
class SeriesSearchView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        search_letter = request.query_params.get("search", "").strip()

        if not search_letter:
            return APIResponse.error("Search parameter is required")

        cache_key = generate_cache_key("series:search", request)
        cached_res = get_cached_response(cache_key)
        if cached_res:
            return cached_res

        queryset = TV_Series.objects.filter(
            title__istartswith=search_letter
        ).order_by("-releaseDate")

        paginator = CustomPagination()
        page = paginator.paginate_queryset(queryset, request)

        serializer = TVSeriesDetailSerializer(page, many=True)

        response = paginator.get_paginated_response(serializer.data)
        set_cached_response(cache_key, response.data)
        return response


# ==========================================
# ALL SERIES
# ==========================================
class AllTVSeriesView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cache_key = generate_cache_key("series:all", request)
        cached_res = get_cached_response(cache_key)
        if cached_res:
            return cached_res

        queryset = TV_Series.objects.exclude(
            Q(title__isnull=True) |
            Q(title="") |
            Q(subjectType__isnull=True)
        ).order_by("-releaseDate")

        paginator = CustomPagination()
        page = paginator.paginate_queryset(queryset, request)

        serializer = TVSeriesSerializer(page, many=True)

        response = paginator.get_paginated_response(serializer.data)
        set_cached_response(cache_key, response.data)
        return response


# ==========================================
# SERIES BY TITLE
# ==========================================
class FilterByTitleView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cache_key = generate_cache_key("series:title", request)
        cached_res = get_cached_response(cache_key)
        if cached_res:
            return cached_res

        title = request.query_params.get("title", "")

        queryset = TV_Series.objects.filter(is_active=True)

        if title:
            queryset = queryset.filter(title__icontains=title)

        queryset = queryset.order_by("-releaseDate")

        paginator = CustomPagination()
        page = paginator.paginate_queryset(queryset, request)

        serializer = TVSeriesDetailSerializer(page, many=True)

        response = paginator.get_paginated_response(serializer.data)
        set_cached_response(cache_key, response.data)
        return response


# ==========================================
# SERIES BY GENRE
# ==========================================
class FilterByGenreView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cache_key = generate_cache_key("series:genre", request)
        cached_res = get_cached_response(cache_key)
        if cached_res:
            return cached_res

        genre = request.query_params.get("genre", "")

        queryset = TV_Series.objects.filter(is_active=True)

        if genre:
            queryset = queryset.filter(genre__name__icontains=genre)

        queryset = queryset.order_by("-releaseDate").distinct()

        paginator = CustomPagination()
        page = paginator.paginate_queryset(queryset, request)

        serializer = TVSeriesDetailSerializer(page, many=True)

        response = paginator.get_paginated_response(serializer.data)
        set_cached_response(cache_key, response.data)
        return response


# ==========================================
# SERIES BY COUNTRY
# ==========================================
class FilterByCountry(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cache_key = generate_cache_key("series:country", request)
        cached_res = get_cached_response(cache_key)
        if cached_res:
            return cached_res

        country = request.query_params.get("country", "")

        queryset = TV_Series.objects.filter(is_active=True)

        if country:
            queryset = queryset.filter(country__name__icontains=country)

        queryset = queryset.order_by("-releaseDate").distinct()

        paginator = CustomPagination()
        page = paginator.paginate_queryset(queryset, request)

        serializer = TVSeriesDetailSerializer(page, many=True)

        response = paginator.get_paginated_response(serializer.data)
        set_cached_response(cache_key, response.data)
        return response


# ==========================================
# SERIES BY ID
# ==========================================
class FilterByIdView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        series_id = request.query_params.get("id")

        if not series_id:
            return APIResponse.error("id is required")

        cache_key = generate_cache_key("series:id", request)
        cached_res = get_cached_response(cache_key)
        if cached_res:
            return cached_res

        try:
            series = TV_Series.objects.get(id=series_id, is_active=True)
        except TV_Series.DoesNotExist:
            return APIResponse.error(
                "Series not found",
                status_code=status.HTTP_404_NOT_FOUND
            )

        serializer = TVSeriesDetailSerializer(series)

        response = APIResponse.success(data=serializer.data)
        set_cached_response(cache_key, response.data)
        return response


# ==========================================
# SERIES FILTERS
# ==========================================
class SeriesSortingFilters(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cache_key = generate_cache_key("series:filter", request)
        cached_res = get_cached_response(cache_key)
        if cached_res:
            return cached_res

        genre = request.query_params.get("genre")
        country = request.query_params.get("country")
        year = request.query_params.get("year")

        filters = Q()

        if genre and genre != "All":
            filters &= Q(genre__name__iexact=genre)

        if country and country != "All":
            filters &= Q(country__name__iexact=country)

        if year and year != "All":
            filters &= Q(**get_year_filter(year))

        queryset = TV_Series.objects.filter(filters).distinct().order_by("-releaseDate")

        paginator = CustomPagination()
        page = paginator.paginate_queryset(queryset, request)

        serializer = TVSeriesSerializer(page, many=True)

        response = paginator.get_paginated_response(serializer.data)
        set_cached_response(cache_key, response.data)
        return response


# ==========================================
# SERIES SORTING
# ==========================================
class SeriesIMDbSortAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cache_key = generate_cache_key("series:sort", request)
        cached_res = get_cached_response(cache_key)
        if cached_res:
            return cached_res

        sort_type = request.query_params.get("type", "imdb")

        queryset = TV_Series.objects.exclude(
            Q(title__isnull=True) |
            Q(title="") |
            Q(subjectType__isnull=True)
        )

        if sort_type == "imdb":
            from_rate = request.query_params.get("from")
            to_rate = request.query_params.get("to")

            filters = Q()

            if from_rate:
                filters &= Q(imdbRate__gte=float(from_rate))

            if to_rate:
                filters &= Q(imdbRate__lte=float(to_rate))

            queryset = queryset.filter(filters).order_by("-imdbRate")

        elif sort_type == "latest":
            queryset = queryset.order_by("-created_at")

        elif sort_type == "hottest":
            queryset = queryset.order_by("-imdbRate")

        else:
            return APIResponse.error("Invalid sort type")

        paginator = CustomPagination()
        page = paginator.paginate_queryset(queryset, request)

        serializer = TVSeriesSerializer(page, many=True)

        response = paginator.get_paginated_response(serializer.data)
        set_cached_response(cache_key, response.data)
        return response


# ==========================================
# SERIES CATEGORY
# ==========================================
class SeriesCategoryView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cache_key = generate_cache_key("series:category", request)
        cached_res = get_cached_response(cache_key)
        if cached_res:
            return cached_res

        size = int(request.query_params.get("size", 3))

        data = {}

        for genre in Genre.objects.all():
            series = TV_Series.objects.filter(
                is_active=True,
                genre=genre
            ).order_by("-releaseDate")[:size]

            if series.exists():
                serializer = TVSeriesSerializer(series, many=True)
                data[genre.name] = serializer.data

        response = APIResponse.success(data=data)
        set_cached_response(cache_key, response.data)
        return response


# ==========================================
# SERIES SCRAPE
# ==========================================
class SeriesScrapeView(APIView):

    def get(self, request):
        try:
            result = process_series_item(
                "series",
                sort="ForYou",
                page=1,
                perPage=50
            )

            serializer = TVSeriesDetailSerializer(result["series"], many=True)

            cache.clear()

            return APIResponse.success(
                data={
                    "created": result["created"],
                    "updated": result["updated"],
                    "series": serializer.data
                },
                message="Scraping completed"
            )

        except Exception as e:
            return APIResponse.error(
                "Scraping failed",
                errors=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ==========================================
# SERIES BY YEAR
# ==========================================
class SeriesByYearAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cache_key = generate_cache_key("series:by_year", request)
        cached_res = get_cached_response(cache_key)
        if cached_res:
            return cached_res

        year = request.GET.get("year", "All")
        filters = get_year_filter(year)

        queryset = TV_Series.objects.filter(**filters).order_by("-releaseDate").distinct()

        paginator = CustomPagination()
        page = paginator.paginate_queryset(queryset, request)

        serializer = TVSeriesSerializer(page, many=True)

        response = paginator.get_paginated_response(serializer.data)
        set_cached_response(cache_key, response.data)
        return response


# ==========================================
# SEARCH LOG
# ==========================================
class SeriesSearchLogAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        name = request.data.get("name")
        year = request.data.get("year")

        if not name:
            return APIResponse.error("name is required")

        if year in ["", "All", None]:
            year = None

        try:
            year = int(year) if year is not None else None
        except:
            return APIResponse.error("year must be a number")

        SearchLog.objects.create(
            type="series",
            name=name.strip(),
            year=year
        )

        return APIResponse.success(message="Logged successfully")