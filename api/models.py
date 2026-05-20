from django.db import models


class Foryou(models.Model):
    title = models.CharField(max_length=100)
    movie = models.ManyToManyField("Movie", blank=True)
    tv_series = models.ManyToManyField("TV_Series", blank=True)
    order_by = models.IntegerField(default=0)
    last_update = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Country(models.Model):
    name = models.CharField(max_length=100, unique=True)
    latitude = models.CharField(max_length=20, null=True, blank=True)
    longitude = models.CharField(max_length=20, null=True, blank=True)
    flag = models.URLField(max_length=500, blank=True)
    code = models.CharField(max_length=2, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Actor(models.Model):
    name = models.CharField(max_length=500)
    image_url = models.URLField(max_length=500, blank=True)
    staff_id = models.CharField(max_length=500, unique=True)

    def __str__(self):
        return self.name


class Role(models.Model):
    actor = models.ForeignKey(Actor, on_delete=models.CASCADE)
    character = models.CharField(max_length=500, blank=True)

    def __str__(self):
        return self.character or "Unknown Role"


class Movie(models.Model):
    subjectId = models.CharField(max_length=255, unique=True)
    title = models.CharField(max_length=255)
    rate = models.FloatField(default=0)
    imdbRate = models.FloatField(null=True, blank=True)
    releaseDate = models.DateField(null=True, blank=True)
    subjectType = models.IntegerField(blank=True, null=True)
    genre = models.ManyToManyField(Genre)
    country = models.ForeignKey(
        Country, on_delete=models.SET_NULL, null=True
    )
    cast = models.ManyToManyField(Role)
    cover = models.JSONField(default=dict)
    image = models.JSONField(default=dict)
    trailer = models.JSONField(default=dict, blank=True, null=True)
    subtitles = models.JSONField(default=dict, blank=True, null=True)
    ops = models.JSONField(default=dict, blank=True, null=True)
    content = models.CharField(max_length=255, blank=True)
    description = models.TextField(null=True, blank=True)
    deepLink = models.URLField(max_length=500, blank=True)
    watch_url = models.URLField(max_length=500, blank=True)
    opItemId = models.IntegerField(blank=True, null=True)
    hasResource = models.BooleanField(default=False)
    seenStatus = models.IntegerField(default=False)
    duration = models.PositiveIntegerField(
        help_text="Duration in seconds",
        blank=True,
        null=True
    )
    seconds = models.PositiveIntegerField(
        help_text="Duration in seconds",
        blank=True,
        null=True
    )
    viewers = models.PositiveIntegerField(
        help_text="Total viewers",
        blank=True,
        null=True
    )
    corner = models.CharField(max_length=255, blank=True)
    more_like_this = models.ManyToManyField(
        "self",
        blank=True,
        related_name="movies"
    )
    detailPath = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class Episode(models.Model):
    subjectId = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    resourceLink = models.URLField(max_length=500, blank=True)
    sourceUrl = models.URLField(max_length=500, null=True, blank=True)
    linkType = models.IntegerField(blank=True, null=True)
    size = models.PositiveIntegerField(blank=True, null=True)
    seasons = models.JSONField(default=dict)
    uploadBy = models.CharField(max_length=255, blank=True)
    resourceId = models.CharField(max_length=1000, null=True, blank=True)
    postId = models.CharField(max_length=255, null=True, blank=True)
    episode = models.IntegerField(blank=True, null=True)
    season = models.IntegerField(blank=True, null=True)
    resolution = models.CharField(max_length=255, blank=True)
    codecName = models.CharField(max_length=255, blank=True)
    duration = models.PositiveIntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.title} | {self.episode}"


class TV_Series(models.Model):
    subjectId = models.CharField(max_length=255, unique=True)
    title = models.CharField(max_length=255)
    rate = models.FloatField(default=0, blank=True)
    imdbRate = models.FloatField(null=True, blank=True)
    subjectType = models.IntegerField(blank=True, null=True)
    releaseDate = models.DateField(blank=True, null=True)
    episode = models.ManyToManyField(Episode)
    genre = models.ManyToManyField(Genre)
    country = models.ForeignKey(
        Country, on_delete=models.SET_NULL, null=True
    )
    cast = models.ManyToManyField(Role)
    cover = models.JSONField(default=dict)
    image = models.JSONField(default=dict)
    trailer = models.JSONField(default=dict, blank=True, null=True)
    description = models.TextField(null=True, blank=True)
    content = models.CharField(max_length=255, blank=True)
    detailPath = models.CharField(max_length=255, blank=True)
    subtitles = models.JSONField(default=dict, blank=True, null=True)
    ops = models.JSONField(default=dict, blank=True, null=True)
    deepLink = models.URLField(max_length=500, blank=True)
    opItemId = models.IntegerField(blank=True, null=True)
    hasResource = models.BooleanField(default=False)
    seenStatus = models.IntegerField(default=False)
    seconds = models.PositiveIntegerField(blank=True, null=True)
    duration = models.PositiveIntegerField(blank=True, null=True)
    viewers = models.PositiveIntegerField(blank=True, null=True)
    corner = models.CharField(max_length=255, blank=True)
    more_like_this = models.ManyToManyField(
        "self",
        blank=True,
        related_name="series"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title

class SearchLog(models.Model):
    TYPE_CHOICES = (
        ("movie", "Movie"),
        ("series", "Series"),
    )

    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    name = models.CharField(max_length=255)
    year = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)