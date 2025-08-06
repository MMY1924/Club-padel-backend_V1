# apps/players/urls_v2.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views_v2 import JugadorViewSet

router = DefaultRouter()
router.register(r'jugadores', JugadorViewSet, basename='jugador')

urlpatterns = [
    path('', include(router.urls)),
]