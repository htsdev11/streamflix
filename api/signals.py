from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache

from .models import Genre, Country, Movie


@receiver([post_save, post_delete], sender=Genre)
def clear_genre_cache(sender, **kwargs):
    cache.delete("genres:list")


@receiver([post_save, post_delete], sender=Country)
def clear_country_cache(sender, **kwargs):
    cache.delete("countries:active")


@receiver([post_save, post_delete], sender=Movie)
def clear_movie_cache(sender, **kwargs):
    cache.delete("movies:years")