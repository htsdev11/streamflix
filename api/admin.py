from django.contrib import admin
from django.db.models import Count

from .models import (
    Foryou,
    Genre,
    Country,
    Actor,
    Role,
    Movie,
    Episode,
    TV_Series,
    SearchLog
)


# ==========================================
# GLOBAL ADMIN SETTINGS
# ==========================================
admin.site.site_header = "MovieBox Admin"
admin.site.site_title = "MovieBox Panel"
admin.site.index_title = "MovieBox Dashboard"


# ==========================================
# FORYOU ADMIN (OPTIMIZED)
# ==========================================
@admin.register(Foryou)
class ForyouAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "order_by",
        "movie_count",
        "series_count",
        "is_active",
        "last_update",
    )

    list_editable = ("order_by", "is_active")
    search_fields = ("title",)
    ordering = ("order_by",)
    filter_horizontal = ("movie", "tv_series")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            total_movies=Count("movie", distinct=True),
            total_series=Count("tv_series", distinct=True)
        )

    def movie_count(self, obj):
        return obj.total_movies

    def series_count(self, obj):
        return obj.total_series


# ==========================================
# GENRE ADMIN
# ==========================================
@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)
    ordering = ("name",)
    list_per_page = 50


# ==========================================
# COUNTRY ADMIN (OPTIMIZED)
# ==========================================
@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code")
    list_editable = ("is_active",)
    list_per_page = 50


# ==========================================
# ACTOR ADMIN
# ==========================================
@admin.register(Actor)
class ActorAdmin(admin.ModelAdmin):
    list_display = ("name", "staff_id")
    search_fields = ("name", "staff_id")
    ordering = ("name",)
    list_per_page = 50


# ==========================================
# ROLE ADMIN
# ==========================================
@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("actor", "character")
    search_fields = ("actor__name", "character")
    autocomplete_fields = ("actor",)
    list_select_related = ("actor",)


# ==========================================
# MOVIE ADMIN (OPTIMIZED)
# ==========================================
@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "subjectId",
        "rate",
        "imdbRate",
        "country",
        "releaseDate",
        "viewers",
        "is_active",
        "updated_at",
    )

    list_filter = (
        "is_active",
        "country",
        "releaseDate",
        "genre",
    )

    search_fields = (
        "title",
        "subjectId",
        "description",
    )

    readonly_fields = ("created_at", "updated_at")

    list_editable = ("is_active",)

    autocomplete_fields = ("country",)

    filter_horizontal = (
        "genre",
        "cast",
        "more_like_this",
    )

    date_hierarchy = "releaseDate"
    ordering = ("-updated_at",)
    list_per_page = 25

    list_select_related = ("country",)


# ==========================================
# EPISODE ADMIN
# ==========================================
@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "season",
        "episode",
        "resolution",
        "duration",
        "is_active",
    )

    list_filter = ("is_active", "season", "resolution")
    search_fields = ("title", "subjectId")
    list_editable = ("is_active",)
    ordering = ("season", "episode")
    list_per_page = 50


# ==========================================
# TV SERIES ADMIN (OPTIMIZED)
# ==========================================
@admin.register(TV_Series)
class TVSeriesAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "subjectId",
        "rate",
        "imdbRate",
        "country",
        "releaseDate",
        "viewers",
        "is_active",
    )

    list_filter = (
        "is_active",
        "country",
        "releaseDate",
        "genre",
    )

    search_fields = (
        "title",
        "subjectId",
        "description",
    )

    readonly_fields = ("created_at", "updated_at")

    autocomplete_fields = ("country",)

    filter_horizontal = (
        "episode",
        "genre",
        "cast",
        "more_like_this",
    )

    list_editable = ("is_active",)

    date_hierarchy = "releaseDate"
    ordering = ("-updated_at",)
    list_per_page = 25

    list_select_related = ("country",)


# ==========================================
# SEARCH LOG ADMIN (OPTIMIZED)
# ==========================================
@admin.register(SearchLog)
class SearchLogAdmin(admin.ModelAdmin):

    list_display = ("id", "type", "name", "year", "created_at")
    list_filter = ("type", "year", "created_at")
    search_fields = ("name",)
    ordering = ("-created_at",)

    readonly_fields = ("created_at",)

    fieldsets = (
        ("Search Info", {
            "fields": ("type", "name", "year")
        }),
        ("Meta", {
            "fields": ("created_at",)
        }),
    )

    list_per_page = 50