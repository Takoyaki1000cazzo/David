from django.urls import path
from . import views

urlpatterns = [
    path('', views.book_list, name='book-list'),
    path('books/<int:pk>/', views.book_detail, name='book-detail'),
    path('favorites/', views.favorite_list, name='favorite-list'),
    path('books/<int:pk>/favorite/add/', views.favorite_add, name='favorite-add'),
    path('books/<int:pk>/favorite/remove/', views.favorite_remove, name='favorite-remove'),
    path('books/<int:pk>/favorite/toggle/', views.favorite_toggle, name='favorite-toggle'),
]
