import random

import requests
from PIL import ImageFile
from django.template.defaultfilters import title
from rest_framework import serializers

from .models import *


class GenreSerializer(serializers.ModelSerializer):

    class Meta:
        model = Genre
        fields = ["id", "name"]


class EpisodeSerializer(serializers.ModelSerializer):

    class Meta:
        model = Episode
        fields = [
            "id",
            "subjectId",
            "title",
            "sourceUrl",
            "season",
            "episode",
            "uploadBy",
            "linkType",
            "codecName",
            "resourceLink",
            "created_at",
            "updated_at",
            "is_active",
        ]


class CountrySerializer(serializers.ModelSerializer):

    class Meta:
        model = Country
        fields = ["name"]


class ActorSerializer(serializers.ModelSerializer):

    class Meta:
        model = Actor
        fields = ["name", "image_url", "staff_id"]


class RoleSerializer(serializers.ModelSerializer):

    actor = ActorSerializer(required=False, read_only=True)

    class Meta:
        model = Role
        fields = "__all__"


class SeriesMoreLikeSerializer(serializers.ModelSerializer):

    class Meta:
        model = Movie
        fields = [
            "id",
            "subjectId",
            "title",
            "imdbRate",
            "subjectType",
            "cover",
            "description",
            "detailPath",
            "duration",
        ]


class TVSeriesDetailSerializer(serializers.ModelSerializer):

    genre = GenreSerializer(required=False, read_only=True, many=True)
    episode = EpisodeSerializer(required=False, read_only=True, many=True)
    country = CountrySerializer(required=False, read_only=True)
    cast = RoleSerializer(required=False, read_only=True, many=True)
    more_like_this = SeriesMoreLikeSerializer(many=True, read_only=True)

    trailer = serializers.SerializerMethodField()
    cover = serializers.SerializerMethodField()

    class Meta:
        model = TV_Series
        fields = [
            "id",
            "subjectId",
            "title",
            "imdbRate",
            "subjectType",
            "releaseDate",
            "description",
            "cover",
            "trailer",
            "detailPath",
            "subtitles",
            "duration",
            "corner",
            "genre",
            "country",
            "episode",
            "cast",
            "more_like_this",
            "created_at",
            "updated_at",
            "is_active",
        ]

    def get_trailer(self, obj):
        if obj.trailer == {}:
            return None
        return obj.trailer

    def get_cover(self, obj):
        if not isinstance(obj.cover, str):
            return obj.cover

        head = requests.head(obj.cover, allow_redirects=True)
        file_size = head.headers.get("Content-Length")

        if file_size:
            file_size = int(file_size)
        else:
            file_size = None

        parser = ImageFile.Parser()

        with requests.get(obj.cover, stream=True) as response:
            for chunk in response.iter_content(1024):
                parser.feed(chunk)

                if parser.image:
                    width, height = parser.image.size
                    break

                width, height = 0, 0

        return {
            "id": "0",
            "gif": None,
            "url": obj.cover,
            "size": file_size,
            "width": width,
            "format": "jpg",
            "height": height,
            "blurHash": None,
            "thumbnail": None,
            "avgHueDark": None,
            "avgHueLight": None,
        }


class MovieMoreLikeSerializer(serializers.ModelSerializer):

    class Meta:
        model = Movie
        fields = [
            "id",
            "subjectId",
            "title",
            "imdbRate",
            "subjectType",
            "cover",
            "description",
            "detailPath",
            "duration",
        ]


class MovieDetailSerializer(serializers.ModelSerializer):

    genre = GenreSerializer(required=False, read_only=True, many=True)
    country = CountrySerializer(required=False, read_only=True)
    cast = RoleSerializer(required=False, read_only=True, many=True)
    more_like_this = MovieMoreLikeSerializer(many=True, read_only=True)

    trailer = serializers.SerializerMethodField()
    cover = serializers.SerializerMethodField()

    class Meta:
        model = Movie
        fields = [
            "id",
            "subjectId",
            "title",
            "imdbRate",
            "subjectType",
            "releaseDate",
            "description",
            "cover",
            "trailer",
            "detailPath",
            "subtitles",
            "duration",
            "corner",
            "genre",
            "country",
            "cast",
            "more_like_this",
            "created_at",
            "updated_at",
            "is_active",
        ]

    def get_trailer(self, obj):
        if obj.trailer == {}:
            return None
        return obj.trailer

    def get_cover(self, obj):
        if not isinstance(obj.cover, str):
            return obj.cover

        head = requests.head(obj.cover, allow_redirects=True)
        file_size = head.headers.get("Content-Length")

        if file_size:
            file_size = int(file_size)
        else:
            file_size = None

        parser = ImageFile.Parser()

        with requests.get(obj.cover, stream=True) as response:
            for chunk in response.iter_content(1024):
                parser.feed(chunk)

                if parser.image:
                    width, height = parser.image.size
                    break

                width, height = 0, 0

        return {
            "id": "0",
            "gif": None,
            "url": obj.cover,
            "size": file_size,
            "width": width,
            "format": "jpg",
            "height": height,
            "blurHash": None,
            "thumbnail": None,
            "avgHueDark": None,
            "avgHueLight": None,
        }


class TVSeriesSerializer(serializers.ModelSerializer):

    country = CountrySerializer(required=False, read_only=True)
    genre = GenreSerializer(required=False, read_only=True, many=True)

    class Meta:
        model = TV_Series
        fields = [
            "id",
            "subjectId",
            "title",
            "subjectType",
            "cover",
            "imdbRate",
            "releaseDate",
            "description",
            "detailPath",
            "duration",
            "country",
            "genre",
        ]


class MovieSerializer(serializers.ModelSerializer):

    country = CountrySerializer(required=False, read_only=True)
    genre = GenreSerializer(required=False, read_only=True, many=True)

    class Meta:
        model = Movie
        fields = [
            "id",
            "subjectId",
            "title",
            "subjectType",
            "cover",
            "imdbRate",
            "releaseDate",
            "description",
            "detailPath",
            "duration",
            "country",
            "genre",
        ]


class ForyouSerializer(serializers.ModelSerializer):

    data = serializers.SerializerMethodField()

    class Meta:
        model = Foryou
        fields = ["id", "title", "data"]

    def get_data(self, obj):
        context = self.context

        movies = MovieSerializer(obj.movie.all(), many=True).data
        series = TVSeriesSerializer(obj.tv_series.all(), many=True).data

        combined = movies + series

        if context.get("paginate"):
            value_of_splice = context.get("value_of_splice")
            random.shuffle(combined)
            combined = combined[:value_of_splice]
        else:
            random.shuffle(combined)

        return combined


class ForyouMoviesSerializer(serializers.ModelSerializer):

    data = serializers.SerializerMethodField()

    class Meta:
        model = Foryou
        fields = ["id", "title", "data"]

    def get_data(self, obj):
        context = self.context
        movie = obj.movie.all()

        if context.get("paginate"):
            value_of_splice = context.get("value_of_splice")

            if isinstance(value_of_splice, int):
                movie = movie[:value_of_splice]

        movies = MovieSerializer(movie, many=True).data

        return movies


class ForyouSeriesSerializer(serializers.ModelSerializer):

    data = serializers.SerializerMethodField()

    class Meta:
        model = Foryou
        fields = ["id", "title", "data"]

    def get_data(self, obj):
        context = self.context

        valid_series = [
            series
            for series in obj.tv_series.all()
            if series.title and series.subjectType is not None
        ]

        if context.get("paginate"):
            value_of_splice = context.get("value_of_splice")

            if isinstance(value_of_splice, int):
                valid_series = valid_series[:value_of_splice]

        series = TVSeriesSerializer(valid_series, many=True).data

        return series