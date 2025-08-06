# apps/players/urls_jwt.py

from django.urls import path
from .authentication import (
    CustomTokenObtainPairView, CustomTokenRefreshView,
    jwt_login, jwt_refresh, jwt_logout, jwt_verify
)

urlpatterns = [
    # JWT Authentication Endpoints
    
    # Metodo 1: Vistas basadas en clase (DRF estándar)
    path('auth/jwt/token/', CustomTokenObtainPairView.as_view(), name='jwt_obtain_pair'),
    path('auth/jwt/token/refresh/', CustomTokenRefreshView.as_view(), name='jwt_refresh'),
    
    # Metodo 2: Vistas funcionales personalizadas (más control)
    path('auth/jwt/login/', jwt_login, name='jwt_login'),
    path('auth/jwt/refresh-token/', jwt_refresh, name='jwt_refresh_custom'),
    path('auth/jwt/logout/', jwt_logout, name='jwt_logout'),
    path('auth/jwt/verify/', jwt_verify, name='jwt_verify'),
]