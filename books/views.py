from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST, require_http_methods

import json
import os
from io import BytesIO

from PIL import Image

from .models import Book, Favorite, Page, ReadingProgress
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
    sort = request.GET.get('sort', 'new')
    if sort == 'title':
        books = books.order_by('title')
    elif sort == 'age':
        books = books.order_by('age_min', 'age_max')
    else:
        sort = 'new'
        books = books.order_by('-created_at')
    books = list(books)
    if request.user.is_authenticated:
        progress_map = {
            progress.book_id: progress.last_page_no
            for progress in ReadingProgress.objects.filter(user=request.user, book__in=books)
        }
        for book in books:
            book.resume_page_no = progress_map.get(book.pk)
        favorite_ids = set(
            Favorite.objects.filter(user=request.user, book__in=books).values_list('book_id', flat=True)
        )
    else:
        for book in books:
            book.resume_page_no = None
        favorite_ids = set()
    return render(request, 'books/book_list.html', {'books': books, 'age': request.GET.get('age', ''), 'sort': sort, 'favorite_ids': favorite_ids})


def book_detail(request, pk):
    # 下書きへの一般アクセスは404にする
    book = get_object_or_404(visible_books(request), pk=pk)
    pages = list(book.pages.all())
    current_no, total, page = resolve_page(pages, request.GET.get('p', '1'))
    nav = next_page_info(current_no, total)
    last_page_no = None
    is_favorite = False
    saved_page_no = None
    if request.user.is_authenticated:
        # 「続きから読む」用: 上書き前の保存ページを保持する（表示後に現在ページで更新される）
        existing = ReadingProgress.objects.filter(user=request.user, book=book).first()
        if existing and total:
            saved_page_no = max(1, min(existing.last_page_no, total))
        # 「続きから読む」用: 詳細表示時に開いているページを保存・更新する
        ReadingProgress.objects.update_or_create(
            user=request.user, book=book, defaults={'last_page_no': current_no})
        last_page_no = current_no
        is_favorite = Favorite.objects.filter(user=request.user, book=book).exists()
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
        'is_favorite': is_favorite,
        'saved_page_no': saved_page_no,
        'is_draft': book.status == Book.STATUS_DRAFT,
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


BULK_EDIT_BOOK_FIELDS = ('title', 'age_min', 'age_max', 'description', 'description_ja', 'status')
BULK_EDIT_PAGE_FIELDS = ('text_en', 'text_ja', 'audio_url')
BULK_EDIT_IMAGE_EXTENSIONS = {'.gif', '.jpg', '.jpeg', '.png', '.webp'}
BULK_EDIT_MAX_IMAGE_SIZE = 5 * 1024 * 1024


def _validate_bulk_image(uploaded):
    """アップロード画像の検証。成功時はファイル内容(bytes)、失敗時はエラー文を返す。"""
    ext = os.path.splitext(uploaded.name)[1].lower()
    if ext not in BULK_EDIT_IMAGE_EXTENSIONS:
        return None, f'対応していない画像形式です: {ext or "(拡張子なし)"}'
    if uploaded.size > BULK_EDIT_MAX_IMAGE_SIZE:
        return None, '画像サイズは5MB以下にしてください。'
    try:
        content = uploaded.read()
    except (OSError, ValueError):
        return None, '画像ファイルを読み取れませんでした。'
    try:
        Image.open(BytesIO(content)).verify()
    except Exception:
        return None, '画像ファイルとして読み取れませんでした。'
    return content, None


def _collect_validation_errors(prefix, validation_error):
    collected = {}
    for field, messages in validation_error.message_dict.items():
        collected[f'{prefix}.{field}'] = list(messages)
    return collected


@staff_member_required
@require_GET
def book_bulk_edit_form(request, pk):
    """一括編集のHTMLフォーム画面（スタッフ専用）。保存はJSが既存APIへPOSTする。"""
    book = get_object_or_404(Book.objects.prefetch_related('pages'), pk=pk)
    pages = list(book.pages.all())
    return render(request, 'books/bulk_edit.html', {'book': book, 'pages': pages})


@require_POST
@transaction.atomic
def book_bulk_edit(request, pk):
    """絵本＋複数ページの一括更新API（スタッフ専用）。

    JSON例: {"book": {"title": ..., "age_min": 3, ...},
             "pages": [{"page_no": 1, "text_en": ...}, ...]}
    画像は multipart で `payload`(JSON文字列)＋`page_image_<page_no>` /
    `cover_image` として送る。存在するpage_noは更新、無ければ新規作成する。
    全件検証してから保存し、不整合があれば何も更新せず400を返す。
    """
    if not request.user.is_authenticated:
        return JsonResponse({'detail': '認証が必要です。'}, status=401)
    if not request.user.is_staff:
        return JsonResponse({'detail': 'スタッフ権限が必要です。'}, status=403)
    book = get_object_or_404(Book.objects.prefetch_related('pages'), pk=pk)

    if request.content_type and 'multipart' in request.content_type:
        try:
            data = json.loads(request.POST.get('payload', '{}'))
        except (ValueError, TypeError):
            return JsonResponse({'errors': {'payload': ['JSONとして読み取れませんでした。']}}, status=400)
        files = request.FILES
    else:
        try:
            data = json.loads(request.body or b'{}')
        except (ValueError, TypeError):
            return JsonResponse({'errors': {'payload': ['JSONとして読み取れませんでした。']}}, status=400)
        files = {}
    if not isinstance(data, dict):
        return JsonResponse({'errors': {'payload': ['オブジェクトで指定してください。']}}, status=400)

    errors = {}

    book_data = data.get('book', {})
    if not isinstance(book_data, dict):
        errors['book'] = ['オブジェクトで指定してください。']
        book_data = {}
    unknown_book_fields = set(book_data) - set(BULK_EDIT_BOOK_FIELDS)
    if unknown_book_fields:
        errors['book'] = [f'更新できないフィールドです: {", ".join(sorted(unknown_book_fields))}']
    for field in ('age_min', 'age_max'):
        if field in book_data and (isinstance(book_data[field], bool) or not isinstance(book_data[field], int)):
            errors[f'book.{field}'] = ['整数で指定してください。']
    for field in ('title', 'description', 'description_ja', 'status'):
        if field in book_data and not isinstance(book_data[field], str):
            errors[f'book.{field}'] = ['文字列で指定してください。']
    if not errors:
        for field in BULK_EDIT_BOOK_FIELDS:
            if field in book_data:
                setattr(book, field, book_data[field])
    cover_file = files.get('cover_image')
    cover_content = None
    if cover_file is not None:
        cover_content, message = _validate_bulk_image(cover_file)
        if message:
            errors['cover_image'] = [message]

    pages_data = data.get('pages', [])
    if not isinstance(pages_data, list):
        errors['pages'] = ['リストで指定してください。']
        pages_data = []
    existing_pages = {page.page_no: page for page in book.pages.all()}
    planned_pages = []
    seen_page_nos = set()
    for index, item in enumerate(pages_data):
        key = f'pages[{index}]'
        if not isinstance(item, dict):
            errors[key] = ['オブジェクトで指定してください。']
            continue
        page_no = item.get('page_no')
        if isinstance(page_no, bool) or not isinstance(page_no, int) or page_no < 1:
            errors[f'{key}.page_no'] = ['page_noは1以上の整数で指定してください。']
            continue
        if page_no in seen_page_nos:
            errors[f'{key}.page_no'] = ['page_noが重複しています。']
            continue
        seen_page_nos.add(page_no)
        if page_no in existing_pages:
            page = existing_pages[page_no]
            is_new = False
        else:
            page = Page(book=book, page_no=page_no)
            is_new = True
        item_has_error = False
        for field in BULK_EDIT_PAGE_FIELDS:
            if field in item:
                if not isinstance(item[field], str):
                    errors[f'{key}.{field}'] = ['文字列で指定してください。']
                    item_has_error = True
                else:
                    setattr(page, field, item[field])
        if is_new and not page.text_en:
            errors[f'{key}.text_en'] = ['新規ページにはtext_enが必要です。']
            item_has_error = True
        image_file = files.get(f'page_image_{page_no}')
        image_content = None
        if image_file is not None:
            image_content, message = _validate_bulk_image(image_file)
            if message:
                errors[f'{key}.image'] = [message]
                item_has_error = True
        if not item_has_error:
            planned_pages.append((page, is_new, image_content,
                                  image_file.name if image_file is not None else None))

    if not errors:
        try:
            book.full_clean()
        except ValidationError as exc:
            errors.update(_collect_validation_errors('book', exc))
        for page, _is_new, _image_content, _image_name in planned_pages:
            try:
                page.full_clean()
            except ValidationError as exc:
                errors.update(_collect_validation_errors(f'pages[page_no={page.page_no}]', exc))

    if errors:
        return JsonResponse({'errors': errors}, status=400)

    book_updated = bool(book_data) or cover_content is not None
    if cover_content is not None:
        book.cover_image.save(cover_file.name, ContentFile(cover_content), save=False)
    if book_updated:
        book.save()
    updated_pages = []
    created_pages = []
    for page, is_new, image_content, image_name in planned_pages:
        if image_content is not None:
            page.image.save(image_name, ContentFile(image_content), save=False)
        page.save()
        (created_pages if is_new else updated_pages).append(page.page_no)
    return JsonResponse({
        'book_id': book.pk,
        'updated_book': book_updated,
        'updated_pages': sorted(updated_pages),
        'created_pages': sorted(created_pages),
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
