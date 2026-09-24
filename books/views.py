from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from .models import Book


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
    books = Book.objects.all().prefetch_related('pages')
    age = request.GET.get('age')
    if age and age.isdigit():
        age = int(age)
        books = books.filter(age_min__lte=age, age_max__gte=age)
    return render(request, 'books/book_list.html', {'books': books, 'age': request.GET.get('age', '')})


def book_detail(request, pk):
    book = get_object_or_404(Book.objects.prefetch_related('pages'), pk=pk)
    pages = list(book.pages.all())
    current_no, total, page = resolve_page(pages, request.GET.get('p', '1'))
    nav = next_page_info(current_no, total)
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
