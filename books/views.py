from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import Book, Favorite, ReadingProgress


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
@require_POST
def favorite_toggle(request, pk):
    book = get_object_or_404(Book, pk=pk)
    favorite, created = Favorite.objects.get_or_create(user=request.user, book=book)
    if not created:
        favorite.delete()
    return redirect('book-detail', pk=book.pk)


@login_required
@require_POST
def progress_update(request, pk):
    book = get_object_or_404(Book, pk=pk)
    try:
        last_page_no = int(request.POST.get('last_page_no', '1'))
    except (ValueError, TypeError):
        last_page_no = 1
    last_page_no = max(1, last_page_no)
    ReadingProgress.objects.update_or_create(
        user=request.user, book=book, defaults={'last_page_no': last_page_no})
    return redirect(f"{reverse('book-detail', args=[book.pk])}?p={last_page_no}")
