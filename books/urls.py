from django.urls import path
from . import views

urlpatterns = [
    path('', views.book_list, name='book-list'),
    path('books/<int:pk>/', views.book_detail, name='book-detail'),
    path('books/<int:pk>/progress/', views.progress_detail, name='progress-detail'),
    path('books/<int:pk>/progress/update/', views.progress_update, name='progress-update'),
]
