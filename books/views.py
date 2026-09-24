from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from .models import Book, ReadingProgress


def book_list(request):
    books = Book.objects.all().prefetch_related('pages')
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
    book = get_object_or_404(Book.objects.prefetch_related('pages'), pk=pk)
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
    return redirect(f'/books/{book.pk}/?p={last_page_no}')


@login_required
@require_GET
def progress_detail(request, pk):
    book = get_object_or_404(Book, pk=pk)
    progress = ReadingProgress.objects.filter(user=request.user, book=book).first()
    return JsonResponse({
        'book_id': book.pk,
        'last_page_no': progress.last_page_no if progress else 1,
    })
