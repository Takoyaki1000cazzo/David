from django.shortcuts import get_object_or_404, render

from .models import Book


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
