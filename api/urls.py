# # urls.py
#
# urls.py

from django.urls import path

# Movies Views
from .movies_views import (
    MovieSearchView,
    AllMoviesView,
    MovieByTitleView,
    MovieByGenreView,
    MovieByCountry,
    MovieByIdView,
    MovieSortingFilters,
    MovieIMDbSortAPIView,
    MoviesCategoryView,
    MovieScrapeView, GenreListAPIView, CountryListAPIView, MovieByYearAPIView, MovieYearListAPIView,
    SearchSuggestionView, MovieSearchLogAPIView,
)

# Series Views
from .series_views import (
    SeriesSearchView,
    AllTVSeriesView,
    FilterByTitleView,
    FilterByGenreView,
    FilterByCountry,
    FilterByIdView,
    SeriesSortingFilters,
    SeriesIMDbSortAPIView,
    SeriesCategoryView,
    SeriesScrapeView, SeriesByYearAPIView, SeriesSearchLogAPIView,
)

# Foryou Views
from .foryou_views import (
    EveryoneSearchView,
    ForyouAll,
    ForyouById,
    ForyouMoviesAPIView,
    ForyouSeriesAPIView,
    ForyouScrapeView,
    TrendingPageAPIView, ForyouCombinedAPIView,
)

urlpatterns = [

    # ==========================================
    # MOVIES
    # ==========================================
    path("movies/search/", MovieSearchView.as_view()),
    path("movies/all/", AllMoviesView.as_view()),
    path("movies/title/", MovieByTitleView.as_view()),
    path("movies/genre/", MovieByGenreView.as_view()),
    path("movies/country/", MovieByCountry.as_view()),
    path("movies/id/", MovieByIdView.as_view()),
    path("movies/filter/", MovieSortingFilters.as_view()),
    path("movies/sort/", MovieIMDbSortAPIView.as_view()),
    path("movies/category/", MoviesCategoryView.as_view()),
    path("movies/scrape/", MovieScrapeView.as_view()),
    path("movies/name_search/", MovieSearchLogAPIView.as_view(), name="movie-search"),

    # ==========================================
    # SERIES
    # ==========================================
    path("series/search/", SeriesSearchView.as_view()),
    path("series/all/", AllTVSeriesView.as_view()),
    path("series/title/", FilterByTitleView.as_view()),
    path("series/genre/", FilterByGenreView.as_view()),
    path("series/country/", FilterByCountry.as_view()),
    path("series/id/", FilterByIdView.as_view()),
    path("series/filter/", SeriesSortingFilters.as_view()),
    path("series/sort/", SeriesIMDbSortAPIView.as_view()),
    path("series/category/", SeriesCategoryView.as_view()),
    path("series/scrape/", SeriesScrapeView.as_view()),
    path("series/by-year/", SeriesByYearAPIView.as_view(), name="series-by-year"),
    path("series/name_search/", SeriesSearchLogAPIView.as_view(), name="series-search"),

    # ==========================================
    # FORYOU
    # ==========================================
    path("foryou/everyone-search/", EveryoneSearchView.as_view()),
    path("foryou/all/", ForyouAll.as_view()),
    path("foryou/id/", ForyouById.as_view()),
    path("foryou/movies/", ForyouMoviesAPIView.as_view()),
    path("foryou/series/", ForyouSeriesAPIView.as_view()),
    path("foryou/trending/", TrendingPageAPIView.as_view()),
    path("foryou/scrape/", ForyouScrapeView.as_view()),

    path("foryou/mix", ForyouCombinedAPIView.as_view()),

    path("genres/", GenreListAPIView.as_view(), name="genre-list"),
    path("countries/", CountryListAPIView.as_view(), name="country-list"),
    path("years/", MovieYearListAPIView.as_view(), name="movie-year-list"),
    path("movies/by-year/", MovieByYearAPIView.as_view(), name="movies-by-year"),
    path("search/suggestions/", SearchSuggestionView.as_view(), name="search-suggestions"),

]







