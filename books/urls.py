from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

urlpatterns = [
    path('', views.book_list, name='book-list'),
    path('books/<int:pk>/', views.book_detail, name='book-detail'),
    path('books/<int:pk>/next/', views.page_next, name='page-next'),
    path('favorites/', views.favorite_list, name='favorite-list'),
    path('books/<int:pk>/favorite/add/', views.favorite_add, name='favorite-add'),
    path('books/<int:pk>/favorite/remove/', views.favorite_remove, name='favorite-remove'),
    path('books/<int:pk>/favorite/', views.favorite_toggle, name='favorite-toggle'),
    path('books/<int:pk>/progress/', views.progress_update, name='progress-update'),
    path('books/<int:pk>/progress/detail/', views.progress_detail, name='progress-detail'),
    path('accounts/signup/', views.signup, name='signup'),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
]
