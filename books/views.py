from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .models import Book, Favorite, ReadingProgress
from .services import copy_book


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


def resolve_page(pages, raw):
    """?p= の値を安全に解釈し (current_no, total, page) を返す。

    文字列・空欄・None は1ページ目、マイナスや総数超えは範囲内に丸める。
    ページが無い絵本の場合は (1, 0, None) を返す。例外を投げない。
    """
    total = len(pages)
    try:
        current_no = int(raw if raw is not None else '1')
    except (ValueError, TypeError):
        current_no = 1
    if total:
        current_no = max(1, min(current_no, total))
    else:
        current_no = 1
    page = pages[current_no - 1] if pages else None
    return current_no, total, page


def next_page_info(current_no, total):
    """自動進行用の次ページ判定。最終ページでは next_page=None で停止信号を返す。"""
    has_prev = current_no > 1
    has_next = current_no < total
    return {
        'current_no': current_no,
        'total': total,
        'has_prev': has_prev,
        'has_next': has_next,
        'prev_page': current_no - 1 if has_prev else None,
        'next_page': current_no + 1 if has_next else None,
    }


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
    current_no, total, page = resolve_page(pages, request.GET.get('p', '1'))
    nav = next_page_info(current_no, total)
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
        'has_prev': nav['has_prev'],
        'has_next': nav['has_next'],
        'prev_no': current_no - 1,
        'next_no': current_no + 1,
        'prev_page': nav['prev_page'],
        'next_page': nav['next_page'],
        'nav': nav,
        'last_page_no': last_page_no,
    }
    return render(request, 'books/book_detail.html', context)


def page_next(request, pk):
    """次ページ取得API: ?p=現在ページ → 次ページ判定をJSONで返す。

    最終ページでは has_next=false / next_page=null / next_url=null で停止信号。
    範囲外の?p=でもクランプして200を返し、存在しない絵本は404。
    """
    book = get_object_or_404(Book.objects.prefetch_related('pages'), pk=pk)
    pages = list(book.pages.all())
    current_no, total, _ = resolve_page(pages, request.GET.get('p', '1'))
    nav = next_page_info(current_no, total)
    data = {
        'book_id': book.pk,
        **nav,
        'next_url': f'/books/{book.pk}/?p={nav["next_page"]}' if nav['next_page'] else None,
    }
    return JsonResponse(data)


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


@login_required
@require_POST
def book_copy(request, pk):
    """絵本の複製API（スタッフ専用）。複製した下書きの詳細へリダイレクトする。"""
    if not request.user.is_staff:
        raise PermissionDenied('スタッフのみ絵本を複製できます。')
    book = get_object_or_404(Book.objects.prefetch_related('pages'), pk=pk)
    new_book = copy_book(book)
    return redirect('book-detail', pk=new_book.pk)
