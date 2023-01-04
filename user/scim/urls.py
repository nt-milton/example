from django.urls import path

from .views import create_user, handle_users

urlpatterns = [
    path('users/<str:user_id>', handle_users, name='handle_users'),
    path('users', create_user, name='create_user'),
]
