# apps/players/urls_auth.py
from django.urls import path
from .views_auth import (
    CustomTokenObtainPairView,
    login_view,
    register_view,
    logout_view,
    user_profile_view,
    verify_token_view
)
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    # Authentication endpoints that match frontend expectations
    path('auth/login/', login_view, name='auth_login'),
    path('auth/register/', register_view, name='auth_register'),
    path('auth/logout/', logout_view, name='auth_logout'),
    path('auth/user/', user_profile_view, name='auth_user'),
    path('auth/verify/', verify_token_view, name='auth_verify'),
    
    # JWT Token endpoints
    path('auth/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]