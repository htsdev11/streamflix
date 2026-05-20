import random

from django.db.models import Q
from django.db.models.functions import ExtractYear
from django.core.cache import cache

from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

from .models import Movie, Genre, Country, TV_Series, SearchLog
from .serializers import (
    MovieSerializer,
    MovieDetailSerializer,
    GenreSerializer,
    CountrySerializer
)
from .pagination import CustomPagination
from .services import process_movie_item, get_year_filter


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
# MOVIE SEARCH
# ==========================================
class MovieSearchView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        search_letter = request.query_params.get("search", "").strip()

        if not search_letter:
            return APIResponse.error("Search parameter is required")

        queryset = Movie.objects.filter(
            title__istartswith=search_letter
        ).order_by("-releaseDate")

        paginator = CustomPagination()
        page = paginator.paginate_queryset(queryset, request)

        serializer = MovieDetailSerializer(page, many=True)

        return paginator.get_paginated_response(serializer.data)


# ==========================================
# ALL MOVIES
# ==========================================
class AllMoviesView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Movie.objects.exclude(
            Q(title__isnull=True) |
            Q(title="") |
            Q(subjectType__isnull=True)
        ).order_by("-releaseDate")

        paginator = CustomPagination()
        page = paginator.paginate_queryset(queryset, request)

        serializer = MovieSerializer(page, many=True)

        return paginator.get_paginated_response(serializer.data)


# ==========================================
# MOVIE BY TITLE
# ==========================================
class MovieByTitleView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        title = request.query_params.get("title", "")

        queryset = Movie.objects.filter(is_active=True)

        if title:
            queryset = queryset.filter(title__icontains=title)

        queryset = queryset.order_by("-releaseDate")

        paginator = CustomPagination()
        page = paginator.paginate_queryset(queryset, request)

        serializer = MovieDetailSerializer(page, many=True)

        return paginator.get_paginated_response(serializer.data)


# ==========================================
# MOVIE BY GENRE
# ==========================================
class MovieByGenreView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        genre = request.query_params.get("genre", "")

        queryset = Movie.objects.filter(is_active=True)

        if genre:
            queryset = queryset.filter(genre__name__icontains=genre)

        queryset = queryset.order_by("-releaseDate")

        paginator = CustomPagination()
        page = paginator.paginate_queryset(queryset, request)

        serializer = MovieDetailSerializer(page, many=True)

        return paginator.get_paginated_response(serializer.data)


# ==========================================
# MOVIE BY COUNTRY
# ==========================================
class MovieByCountry(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        country = request.query_params.get("country", "")

        queryset = Movie.objects.filter(is_active=True)

        if country:
            queryset = queryset.filter(country__name__icontains=country)

        queryset = queryset.order_by("-releaseDate").distinct()

        paginator = CustomPagination()
        page = paginator.paginate_queryset(queryset, request)

        serializer = MovieDetailSerializer(page, many=True)

        return paginator.get_paginated_response(serializer.data)


# ==========================================
# MOVIE BY ID
# ==========================================
class MovieByIdView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        movie_id = request.query_params.get("id")

        if not movie_id:
            return APIResponse.error("id is required")

        try:
            movie = Movie.objects.get(id=movie_id, is_active=True)
        except Movie.DoesNotExist:
            return APIResponse.error(
                "Movie not found",
                status_code=status.HTTP_404_NOT_FOUND
            )

        serializer = MovieDetailSerializer(movie)

        return APIResponse.success(data=serializer.data)


# ==========================================
# MOVIE FILTERS
# ==========================================
class MovieSortingFilters(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
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

        queryset = Movie.objects.filter(filters).distinct().order_by("-releaseDate")

        paginator = CustomPagination()
        page = paginator.paginate_queryset(queryset, request)

        serializer = MovieSerializer(page, many=True)

        return paginator.get_paginated_response(serializer.data)


# ==========================================
# MOVIE SORTING
# ==========================================
class MovieIMDbSortAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sort_type = request.query_params.get("type", "imdb")

        queryset = Movie.objects.exclude(
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

        serializer = MovieSerializer(page, many=True)

        return paginator.get_paginated_response(serializer.data)


# ==========================================
# MOVIE CATEGORY
# ==========================================
class MoviesCategoryView(APIView):

    def get(self, request):
        size = int(request.query_params.get("size", 3))

        data = []

        for genre in Genre.objects.all():
            movies = Movie.objects.filter(
                is_active=True,
                genre=genre
            ).order_by("-releaseDate")[:size]

            if movies.exists():
                serializer = MovieSerializer(movies, many=True)

                data.append({
                    "name": genre.name,
                    "data": serializer.data
                })

        return APIResponse.success(data=data)


# ==========================================
# MOVIE SCRAPE
# ==========================================
class MovieScrapeView(APIView):

    def get(self, request):
        try:
            result = process_movie_item("movies", sort="ForYou", page=1, perPage=50)

            serializer = MovieDetailSerializer(result["movies"], many=True)

            return APIResponse.success(data={
                "created": result["created"],
                "updated": result["updated"],
                "movies": serializer.data
            }, message="Scraping completed")

        except Exception as e:
            return APIResponse.error(
                "Scraping failed",
                errors=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ==========================================
# MOVIE BY YEAR
# ==========================================
class MovieByYearAPIView(APIView):

    def get(self, request):
        year = request.GET.get("year", "All")
        filters = get_year_filter(year)

        queryset = Movie.objects.filter(**filters).order_by("-releaseDate").distinct()

        paginator = CustomPagination()
        page = paginator.paginate_queryset(queryset, request)

        serializer = MovieSerializer(page, many=True)

        return paginator.get_paginated_response(serializer.data)


# ==========================================
# GENRE LIST
# ==========================================
class GenreListAPIView(APIView):

    def get(self, request):
        cache_key = "genres:list"
        data = cache.get(cache_key)

        if not data:
            genres = Genre.objects.all().order_by("name")
            data = GenreSerializer(genres, many=True).data
            cache.set(cache_key, data, 86400)

        return APIResponse.success(data=data)


# ==========================================
# COUNTRY LIST
# ==========================================
class CountryListAPIView(APIView):

    def get(self, request):
        cache_key = "countries:list"
        data = cache.get(cache_key)

        if not data:
            countries = Country.objects.filter(is_active=True).order_by("name")
            data = CountrySerializer(countries, many=True).data
            cache.set(cache_key, data, 86400)

        return APIResponse.success(data=data)


# ==========================================
# YEAR LIST
# ==========================================
class MovieYearListAPIView(APIView):

    def get(self, request):
        cache_key = "movies:years"
        data = cache.get(cache_key)

        if not data:
            years = (
                Movie.objects.exclude(releaseDate__isnull=True)
                .annotate(year=ExtractYear("releaseDate"))
                .values_list("year", flat=True)
                .distinct()
                .order_by("-year")
            )

            data = {"years": list(years)}
            cache.set(cache_key, data, 86400)

        return APIResponse.success(data=data)


class SearchSuggestionView(APIView):

    def get(self, request):
        search_query = request.query_params.get("search", "").strip()

        if not search_query:
            return APIResponse.error("Search parameter is required")

        series_queryset = TV_Series.objects.filter(
            title__icontains=search_query
        ).order_by("-releaseDate")[:5]

        movie_queryset = Movie.objects.filter(
            title__icontains=search_query
        ).order_by("-releaseDate")[:5]

        suggestions = []

        for series in series_queryset:
            suggestions.append({
                "id": series.id,
                "title": series.title,
                "subjectType": series.subjectType
            })

        for movie in movie_queryset:
            suggestions.append({
                "id": movie.id,
                "title": movie.title,
                "subjectType": movie.subjectType
            })

        return APIResponse.success(data=suggestions)

# ==========================================
# SEARCH LOG
# ==========================================
class MovieSearchLogAPIView(APIView):

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
            type="movie",
            name=name.strip(),
            year=year
        )

        return APIResponse.success(message="Logged successfully")