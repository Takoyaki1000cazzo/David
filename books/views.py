from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_http_methods

from .models import Book, Favorite


def book_list(request):
    books = Book.objects.all().prefetch_related('pages')
    age = request.GET.get('age')
    if age and age.isdigit():
        age = int(age)
        books = books.filter(age_min__lte=age, age_max__gte=age)
    return render(request, 'books/book_list.html', {'books': books, 'age': request.GET.get('age', '')})


def book_detail(request, pk):
    book = get_object_or_404(Book.objects.prefetch_related('pages'), pk=pk)
    pages = list(book.pages.all())
    total = len(pages)
    try:
        current_no = int(request.GET.get('p', '1'))
    except ValueError:
        current_no = 1
    current_no = max(1, min(current_no, total) if total else 1)
    page = pages[current_no - 1] if pages else None
    context = {
        'book': book,
        'page': page,
        'current_no': current_no,
        'total': total,
        'has_prev': current_no > 1,
        'has_next': current_no < total,
        'prev_no': current_no - 1,
        'next_no': current_no + 1,
    }
    return render(request, 'books/book_detail.html', context)


def _safe_redirect(request, default_name, **kwargs):
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url and next_url.startswith('/'):
        return redirect(next_url)
    return redirect(default_name, **kwargs)


@login_required
def favorite_list(request):
    favorites = Favorite.objects.filter(user=request.user).select_related('book').order_by('-created_at')
    return render(request, 'books/favorite_list.html', {'favorites': favorites})


@login_required
@require_POST
def favorite_add(request, pk):
    book = get_object_or_404(Book, pk=pk)
    Favorite.objects.get_or_create(user=request.user, book=book)
    return _safe_redirect(request, 'book-detail', pk=book.pk)


@login_required
@require_http_methods(['POST', 'DELETE'])
def favorite_remove(request, pk):
    book = get_object_or_404(Book, pk=pk)
    Favorite.objects.filter(user=request.user, book=book).delete()
    return _safe_redirect(request, 'favorite-list')


@login_required
@require_POST
def favorite_toggle(request, pk):
    book = get_object_or_404(Book, pk=pk)
    favorite, created = Favorite.objects.get_or_create(user=request.user, book=book)
    if not created:
        favorite.delete()
    return _safe_redirect(request, 'book-detail', pk=book.pk)
