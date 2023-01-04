from django.urls import path

from .views import auth_view, index_view, login_view, logout_view

urlpatterns = [
    path('', index_view, name='home'),
    path('login', login_view, name='login'),
    path('auth', auth_view, name='auth'),
    path('logout', logout_view, name='logout'),
]
