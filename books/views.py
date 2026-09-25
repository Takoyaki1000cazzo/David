from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .models import Book, Favorite, ReadingProgress


def visible_books(request):
    """公開状態に応じた閲覧可能クエリセットを返す。

    一般ユーザー（未ログイン・一般ログイン）は公開済みのみ。
    スタッフはプレビュー用に下書きも含める。
    """
    qs = Book.objects.all().prefetch_related('pages')
    user = request.user
    if not (user.is_authenticated and user.is_staff):
        qs = qs.filter(status=Book.STATUS_PUBLISHED)
    return qs


def book_list(request):
    books = visible_books(request)
    age = request.GET.get('age')
    if age and age.isdigit():
        age = int(age)
        books = books.filter(age_min__lte=age, age_max__gte=age)
    books = list(books)
    if request.user.is_authenticated:
        progress_map = {
            progress.book_id: progress.last_page_no
            for progress in ReadingProgress.objects.filter(user=request.user, book__in=books)
        }
        for book in books:
            book.resume_page_no = progress_map.get(book.pk)
    else:
        for book in books:
            book.resume_page_no = None
    return render(request, 'books/book_list.html', {'books': books, 'age': request.GET.get('age', '')})


def book_detail(request, pk):
    # 下書きへの一般アクセスは404にする
    book = get_object_or_404(visible_books(request), pk=pk)
    pages = list(book.pages.all())
    total = len(pages)
    try:
        current_no = int(request.GET.get('p', '1'))
    except ValueError:
        current_no = 1
    current_no = max(1, min(current_no, total) if total else 1)
    page = pages[current_no - 1] if pages else None
    last_page_no = None
    if request.user.is_authenticated:
        # 「続きから読む」用: 詳細表示時に開いているページを保存・更新する
        ReadingProgress.objects.update_or_create(
            user=request.user, book=book, defaults={'last_page_no': current_no})
        last_page_no = current_no
    context = {
        'book': book,
        'page': page,
        'current_no': current_no,
        'total': total,
        'has_prev': current_no > 1,
        'has_next': current_no < total,
        'prev_no': current_no - 1,
        'next_no': current_no + 1,
        'last_page_no': last_page_no,
    }
    return render(request, 'books/book_detail.html', context)


def _parse_page_no(request):
    raw = request.POST.get('last_page_no', request.POST.get('p', '1'))
    try:
        page_no = int(raw)
    except (ValueError, TypeError):
        page_no = 1
    return max(1, page_no)


def _safe_redirect(request, default_name, **kwargs):
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url and next_url.startswith('/'):
        return redirect(next_url)
    return redirect(default_name, **kwargs)


def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('book-list')
    else:
        form = UserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})


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


@login_required
@require_POST
def progress_update(request, pk):
    book = get_object_or_404(Book, pk=pk)
    last_page_no = _parse_page_no(request)
    ReadingProgress.objects.update_or_create(
        user=request.user, book=book, defaults={'last_page_no': last_page_no})
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url and next_url.startswith('/'):
        return redirect(next_url)
    return redirect(f"{reverse('book-detail', args=[book.pk])}?p={last_page_no}")


@login_required
@require_GET
def progress_detail(request, pk):
    book = get_object_or_404(Book, pk=pk)
    progress = ReadingProgress.objects.filter(user=request.user, book=book).first()
    return JsonResponse({
        'book_id': book.pk,
        'last_page_no': progress.last_page_no if progress else 1,
    })
