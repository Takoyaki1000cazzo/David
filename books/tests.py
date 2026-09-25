import datetime
import json
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.forms import modelform_factory
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Book, Favorite, Page, ReadingProgress
from .services import copy_book


class BookModelTests(TestCase):
    def test_age_reversed_raises_validation_error(self):
        book = Book(title='Test', age_min=6, age_max=3)
        with self.assertRaises(ValidationError):
            book.full_clean()

    def test_age_equal_passes(self):
        book = Book(title='Test', age_min=3, age_max=3)
        book.full_clean()

    def test_age_normal_passes(self):
        book = Book(title='Test', age_min=2, age_max=5)
        book.full_clean()

    def test_status_defaults_to_draft(self):
        book = Book.objects.create(title='Test', age_min=2, age_max=5)
        self.assertEqual(book.status, Book.STATUS_DRAFT)
        self.assertIsNone(book.published_at)

    def test_status_can_be_published(self):
        book = Book.objects.create(
            title='Test', age_min=2, age_max=5,
            status=Book.STATUS_PUBLISHED)
        book.full_clean()
        self.assertEqual(book.status, Book.STATUS_PUBLISHED)


class BookValidationTests(TestCase):
    """#41: 年齢の範囲と画像バリデーション"""

    def test_age_over_12_raises_validation_error(self):
        book = Book(title='Test', age_min=2, age_max=13)
        with self.assertRaises(ValidationError):
            book.full_clean()

    def test_age_min_over_12_raises_validation_error(self):
        book = Book(title='Test', age_min=13, age_max=13)
        with self.assertRaises(ValidationError):
            book.full_clean()

    def test_invalid_image_extension_raises_validation_error(self):
        book = Book(title='Test', age_min=2, age_max=5)
        book.cover_image = SimpleUploadedFile('cover.gif', b'GIF89a', content_type='image/gif')
        with self.assertRaises(ValidationError):
            book.full_clean()

    def test_oversized_image_raises_validation_error(self):
        book = Book(title='Test', age_min=2, age_max=5)
        big = b'\x89PNG\r\n' + b'0' * (5 * 1024 * 1024 + 1)
        book.cover_image = SimpleUploadedFile('cover.png', big, content_type='image/png')
        with self.assertRaises(ValidationError):
            book.full_clean()

    def test_valid_image_passes(self):
        book = Book(title='Test', age_min=2, age_max=5)
        book.cover_image = SimpleUploadedFile('cover.png', b'\x89PNG\r\n', content_type='image/png')
        book.full_clean()


class PageValidationTests(TestCase):
    """#41: 英文必須とページ画像バリデーション"""

    def setUp(self):
        self.book = Book.objects.create(title='Test', age_min=2, age_max=5)

    def test_empty_text_en_raises_validation_error(self):
        page = Page(book=self.book, page_no=1, text_en='   ')
        with self.assertRaises(ValidationError):
            page.full_clean()

    def test_invalid_image_extension_raises_validation_error(self):
        page = Page(book=self.book, page_no=1, text_en='Hello')
        page.image = SimpleUploadedFile('page.txt', b'hello', content_type='text/plain')
        with self.assertRaises(ValidationError):
            page.full_clean()


class AdminFormValidationTests(TestCase):
    """#41: adminフォーム経由でも不正入力を拒否できること"""

    def test_book_form_rejects_age_over_12(self):
        BookForm = modelform_factory(Book, fields='__all__')
        form = BookForm(data={'title': 'Test', 'age_min': 2, 'age_max': 13, 'status': 'draft'})
        self.assertFalse(form.is_valid())

    def test_book_form_rejects_invalid_image(self):
        BookForm = modelform_factory(Book, fields='__all__')
        form = BookForm(
            data={'title': 'Test', 'age_min': 2, 'age_max': 5, 'status': 'draft'},
            files={'cover_image': SimpleUploadedFile('x.gif', b'GIF89a', content_type='image/gif')},
        )
        self.assertFalse(form.is_valid())
        self.assertIn('cover_image', form.errors)

    def test_page_form_rejects_empty_text_en(self):
        book = Book.objects.create(title='Test', age_min=2, age_max=5)
        PageForm = modelform_factory(Page, fields='__all__')
        form = PageForm(data={'book': book.pk, 'page_no': 1, 'text_en': '   '})
        self.assertFalse(form.is_valid())
        self.assertIn('text_en', form.errors)


class PageModelTests(TestCase):
    def test_duplicate_page_no_raises_integrity_error(self):
        book = Book.objects.create(title='Test', age_min=2, age_max=5)
        Page.objects.create(book=book, page_no=1, text_en='Hello')
        with self.assertRaises(IntegrityError):
            Page.objects.create(book=book, page_no=1, text_en='Hello again')

    def test_different_page_no_passes(self):
        book = Book.objects.create(title='Test', age_min=2, age_max=5)
        Page.objects.create(book=book, page_no=1, text_en='Hello')
        Page.objects.create(book=book, page_no=2, text_en='World')
        self.assertEqual(book.pages.count(), 2)


class BookViewEmptyFieldsTests(TestCase):
    def test_book_list_with_empty_description(self):
        """説明文が空でも一覧画面が表示される"""
        book = Book.objects.create(title='Test Book', age_min=2, age_max=5, status=Book.STATUS_PUBLISHED)
        response = self.client.get(reverse('book-list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Book')

    def test_book_list_with_empty_cover(self):
        """表紙画像が空でも一覧画面が表示される"""
        book = Book.objects.create(title='Test Book', age_min=2, age_max=5, status=Book.STATUS_PUBLISHED)
        response = self.client.get(reverse('book-list'))
        self.assertEqual(response.status_code, 200)

    def test_book_detail_with_empty_fields(self):
        """説明文・表紙が空でも詳細画面が表示される"""
        book = Book.objects.create(title='Test Book', age_min=2, age_max=5, status=Book.STATUS_PUBLISHED)
        Page.objects.create(book=book, page_no=1, text_en='Hello')
        response = self.client.get(reverse('book-detail', args=[book.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Book')

    def test_book_detail_with_empty_page_image(self):
        """ページ画像が空でも詳細画面が表示される"""
        book = Book.objects.create(title='Test Book', age_min=2, age_max=5, status=Book.STATUS_PUBLISHED)
        Page.objects.create(book=book, page_no=1, text_en='Hello', text_ja='こんにちは')
        response = self.client.get(reverse('book-detail', args=[book.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hello')


class BookDetailPageValidationTests(TestCase):
    """D6: ?p= に不正値が渡されてもエラーにならず安全に動くこと"""

    def setUp(self):
        self.book = Book.objects.create(title='Test Book', age_min=2, age_max=5, status=Book.STATUS_PUBLISHED)
        Page.objects.create(book=self.book, page_no=1, text_en='Page One')
        Page.objects.create(book=self.book, page_no=2, text_en='Page Two')
        self.url = reverse('book-detail', args=[self.book.pk])

    def test_p_string_falls_back_to_first_page(self):
        """?p=abc（文字列）は1ページ目にフォールバックする"""
        response = self.client.get(self.url, {'p': 'abc'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['current_no'], 1)
        self.assertContains(response, 'Page One')

    def test_p_negative_falls_back_to_first_page(self):
        """?p=-5（マイナス）は1ページ目に丸められる"""
        response = self.client.get(self.url, {'p': '-5'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['current_no'], 1)
        self.assertContains(response, 'Page One')

    def test_p_too_large_clamps_to_last_page(self):
        """?p=999（存在しない大きな数値）は最終ページに丸められる"""
        response = self.client.get(self.url, {'p': '999'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['current_no'], 2)
        self.assertEqual(response.context['total'], 2)
        self.assertContains(response, 'Page Two')

    def test_p_empty_falls_back_to_first_page(self):
        """?p=（空欄）は1ページ目にフォールバックする"""
        response = self.client.get(f'{self.url}?p=')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['current_no'], 1)
        self.assertContains(response, 'Page One')


class AutoNextPageTests(TestCase):
    """自動次ページ: 次ページ判定・最終ページ停止・範囲外の安全処理"""

    def setUp(self):
        self.book = Book.objects.create(title='Next Book', age_min=2, age_max=5, status=Book.STATUS_PUBLISHED)
        Page.objects.create(book=self.book, page_no=1, text_en='Page One')
        Page.objects.create(book=self.book, page_no=2, text_en='Page Two')
        Page.objects.create(book=self.book, page_no=3, text_en='Page Three')
        self.url = reverse('book-detail', args=[self.book.pk])
        self.api_url = reverse('page-next', args=[self.book.pk])

    def test_middle_page_returns_next_page(self):
        """途中ページでは次のページ番号を返す"""
        response = self.client.get(self.url, {'p': '1'})
        self.assertEqual(response.context['has_next'], True)
        self.assertEqual(response.context['next_page'], 2)
        data = self.client.get(self.api_url, {'p': '1'}).json()
        self.assertEqual(data, {
            'book_id': self.book.pk, 'current_no': 1, 'total': 3,
            'has_prev': False, 'has_next': True,
            'prev_page': None, 'next_page': 2,
            'next_url': f'/books/{self.book.pk}/?p=2',
        })

    def test_last_page_returns_stop_signal(self):
        """最終ページでは has_next=false / next_page=null で停止信号を返す"""
        response = self.client.get(self.url, {'p': '3'})
        self.assertEqual(response.context['has_next'], False)
        self.assertIsNone(response.context['next_page'])
        data = self.client.get(self.api_url, {'p': '3'}).json()
        self.assertEqual(data['has_next'], False)
        self.assertIsNone(data['next_page'])
        self.assertIsNone(data['next_url'])

    def test_first_page_has_no_prev(self):
        """1ページ目では prev_page=None を返す"""
        data = self.client.get(self.api_url, {'p': '1'}).json()
        self.assertEqual(data['has_prev'], False)
        self.assertIsNone(data['prev_page'])

    def test_api_out_of_range_is_safe(self):
        """範囲外の?p=でも500にならず丸めて処理する"""
        data = self.client.get(self.api_url, {'p': '-5'}).json()
        self.assertEqual(data['current_no'], 1)
        data = self.client.get(self.api_url, {'p': '999'}).json()
        self.assertEqual(data['current_no'], 3)
        self.assertFalse(data['has_next'])
        self.assertIsNone(data['next_page'])

    def test_api_invalid_p_falls_back_to_first(self):
        """?p=abc・空欄は1ページ目にフォールバックする"""
        self.assertEqual(self.client.get(self.api_url, {'p': 'abc'}).json()['current_no'], 1)
        response = self.client.get(f'{self.api_url}?p=')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['current_no'], 1)

    def test_api_missing_book_returns_404(self):
        """存在しない絵本は404（500ではない）"""
        response = self.client.get(reverse('page-next', args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_book_without_pages_is_safe(self):
        """ページ無しの絵本でもエラーにならず停止信号を返す"""
        empty = Book.objects.create(title='Empty', age_min=1, age_max=2, status=Book.STATUS_PUBLISHED)
        response = self.client.get(reverse('book-detail', args=[empty.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['has_next'])
        self.assertIsNone(response.context['next_page'])
        data = self.client.get(reverse('page-next', args=[empty.pk])).json()
        self.assertFalse(data['has_next'])
        self.assertIsNone(data['next_page'])
        self.assertIsNone(data['next_url'])


class BookViewTests(TestCase):
    """D4a: 一覧・詳細・年齢絞り込みの画面動作チェック"""

    def test_book_list_returns_200(self):
        """一覧ページ `/` は HTTP 200 を返す"""
        Book.objects.create(title='List Check Book', age_min=3, age_max=6, status=Book.STATUS_PUBLISHED)
        response = self.client.get(reverse('book-list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'List Check Book')

    def test_book_detail_returns_200(self):
        """詳細ページ `/books/<id>/` は HTTP 200 を返す"""
        book = Book.objects.create(title='Detail Check Book', age_min=3, age_max=6, status=Book.STATUS_PUBLISHED)
        Page.objects.create(book=book, page_no=1, text_en='Hello')
        response = self.client.get(reverse('book-detail', args=[book.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Detail Check Book')

    def test_book_list_age_filter(self):
        """`/?age=4` は対象(3-6歳)のみ表示し対象外(1-2歳)を表示しない"""
        Book.objects.create(title='Target Age Book', age_min=3, age_max=6, status=Book.STATUS_PUBLISHED)
        Book.objects.create(title='Out Of Range Book', age_min=1, age_max=2, status=Book.STATUS_PUBLISHED)
        response = self.client.get(reverse('book-list'), {'age': '4'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Target Age Book')
        self.assertNotContains(response, 'Out Of Range Book')


class BookListSortTests(TestCase):
    """#54 一覧の並び替え: タイトル順・年齢順・新着順と絞り込み併用"""

    def setUp(self):
        from django.utils import timezone
        base = timezone.now()
        self.zebra = Book.objects.create(title='Zebra Book', age_min=0, age_max=1, status=Book.STATUS_PUBLISHED)
        self.apple = Book.objects.create(title='Apple Book', age_min=0, age_max=2, status=Book.STATUS_PUBLISHED)
        self.mango = Book.objects.create(title='Mango Book', age_min=3, age_max=6, status=Book.STATUS_PUBLISHED)
        Book.objects.filter(pk=self.zebra.pk).update(created_at=base - datetime.timedelta(days=3))
        Book.objects.filter(pk=self.apple.pk).update(created_at=base - datetime.timedelta(days=2))
        Book.objects.filter(pk=self.mango.pk).update(created_at=base - datetime.timedelta(days=1))

    def _titles(self, response):
        return [book.title for book in response.context['books']]

    def test_default_order_is_newest_first(self):
        """未指定は新着順（Mango → Apple → Zebra）"""
        response = self.client.get(reverse('book-list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._titles(response), ['Mango Book', 'Apple Book', 'Zebra Book'])

    def test_sort_title(self):
        """sort=title はタイトル順"""
        response = self.client.get(reverse('book-list'), {'sort': 'title'})
        self.assertEqual(self._titles(response), ['Apple Book', 'Mango Book', 'Zebra Book'])

    def test_sort_age(self):
        """sort=age は年齢順（age_min, age_max）"""
        response = self.client.get(reverse('book-list'), {'sort': 'age'})
        self.assertEqual(self._titles(response), ['Zebra Book', 'Apple Book', 'Mango Book'])

    def test_sort_invalid_falls_back_to_newest(self):
        """不正値は新着順にフォールバックする"""
        response = self.client.get(reverse('book-list'), {'sort': 'hoge'})
        self.assertEqual(response.context['sort'], 'new')
        self.assertEqual(self._titles(response), ['Mango Book', 'Apple Book', 'Zebra Book'])

    def test_sort_combines_with_age_filter(self):
        """年齢絞り込みと併用できる（age=1 は Apple・Zebra のみ）"""
        response = self.client.get(reverse('book-list'), {'age': '1', 'sort': 'title'})
        self.assertEqual(self._titles(response), ['Apple Book', 'Zebra Book'])
        response = self.client.get(reverse('book-list'), {'age': '1', 'sort': 'age'})
        self.assertEqual(self._titles(response), ['Zebra Book', 'Apple Book'])

    def test_sort_select_shows_current(self):
        """切替UIで現在の並び順が選択状態になる"""
        response = self.client.get(reverse('book-list'), {'sort': 'title'})
        self.assertContains(response, '<select name="sort"')
        self.assertContains(response, '<option value="title" selected>')


class ReadingProgressModelTests(TestCase):
    """「続きから読む」用: 1ユーザー1絵本1レコードで最終ページを保持する"""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='reader1', password='pass')
        self.book = Book.objects.create(title='Test', age_min=2, age_max=5)

    def test_create_progress(self):
        p = ReadingProgress.objects.create(user=self.user, book=self.book, last_page_no=3)
        self.assertEqual(p.last_page_no, 3)

    def test_duplicate_user_book_raises_integrity_error(self):
        ReadingProgress.objects.create(user=self.user, book=self.book, last_page_no=1)
        with self.assertRaises(IntegrityError):
            ReadingProgress.objects.create(user=self.user, book=self.book, last_page_no=2)

    def test_update_or_create_does_not_duplicate(self):
        ReadingProgress.objects.update_or_create(
            user=self.user, book=self.book, defaults={'last_page_no': 2})
        ReadingProgress.objects.update_or_create(
            user=self.user, book=self.book, defaults={'last_page_no': 4})
        self.assertEqual(ReadingProgress.objects.count(), 1)
        self.assertEqual(
            ReadingProgress.objects.get(user=self.user, book=self.book).last_page_no, 4)

    def test_different_user_or_book_passes(self):
        User = get_user_model()
        other = User.objects.create_user(username='reader2', password='pass')
        other_book = Book.objects.create(title='Other', age_min=1, age_max=3)
        ReadingProgress.objects.create(user=self.user, book=self.book, last_page_no=1)
        ReadingProgress.objects.create(user=other, book=self.book, last_page_no=1)
        ReadingProgress.objects.create(user=self.user, book=other_book, last_page_no=1)
        self.assertEqual(ReadingProgress.objects.count(), 3)


class FavoriteModelTests(TestCase):
    """お気に入り: 1ユーザー1絵本1レコードで重複登録を防ぐ"""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='fav1', password='pass')
        self.book = Book.objects.create(title='Test', age_min=2, age_max=5)

    def test_create_favorite(self):
        f = Favorite.objects.create(user=self.user, book=self.book)
        self.assertEqual(Favorite.objects.count(), 1)
        self.assertEqual(str(f), f'{self.user} ♥ {self.book.title}')

    def test_duplicate_user_book_raises_integrity_error(self):
        Favorite.objects.create(user=self.user, book=self.book)
        with self.assertRaises(IntegrityError):
            Favorite.objects.create(user=self.user, book=self.book)

    def test_get_or_create_does_not_duplicate(self):
        Favorite.objects.get_or_create(user=self.user, book=self.book)
        Favorite.objects.get_or_create(user=self.user, book=self.book)
        self.assertEqual(Favorite.objects.count(), 1)

    def test_different_user_or_book_passes(self):
        User = get_user_model()
        other = User.objects.create_user(username='fav2', password='pass')
        other_book = Book.objects.create(title='Other', age_min=1, age_max=3)
        Favorite.objects.create(user=self.user, book=self.book)
        Favorite.objects.create(user=other, book=self.book)
        Favorite.objects.create(user=self.user, book=other_book)
        self.assertEqual(Favorite.objects.count(), 3)


class StatusVisibilityTests(TestCase):
    """公開/下書きの出し分け・スタッフ権限・404制限の動作チェック"""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='general', password='testpass123')
        self.staff = User.objects.create_user(username='staff', password='testpass123', is_staff=True)
        self.published = Book.objects.create(
            title='Published Book', age_min=3, age_max=6, status=Book.STATUS_PUBLISHED)
        self.draft = Book.objects.create(
            title='Draft Book', age_min=3, age_max=6, status=Book.STATUS_DRAFT)

    def test_anonymous_list_shows_only_published(self):
        """未ログインの一覧には公開済みのみ表示する"""
        response = self.client.get(reverse('book-list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Published Book')
        self.assertNotContains(response, 'Draft Book')

    def test_anonymous_draft_detail_returns_404(self):
        """未ログインの下書き詳細アクセスは404を返す"""
        response = self.client.get(reverse('book-detail', args=[self.draft.pk]))
        self.assertEqual(response.status_code, 404)

    def test_general_user_list_shows_only_published(self):
        """一般ログインの一覧には公開済みのみ表示する"""
        self.client.login(username='general', password='testpass123')
        response = self.client.get(reverse('book-list'))
        self.assertContains(response, 'Published Book')
        self.assertNotContains(response, 'Draft Book')

    def test_general_user_draft_detail_returns_404(self):
        """一般ログインの下書き詳細アクセスは404を返す"""
        self.client.login(username='general', password='testpass123')
        response = self.client.get(reverse('book-detail', args=[self.draft.pk]))
        self.assertEqual(response.status_code, 404)

    def test_staff_list_shows_draft(self):
        """スタッフの一覧には下書きも表示する（プレビュー用）"""
        self.client.login(username='staff', password='testpass123')
        response = self.client.get(reverse('book-list'))
        self.assertContains(response, 'Published Book')
        self.assertContains(response, 'Draft Book')

    def test_staff_draft_detail_returns_200(self):
        """スタッフは下書き詳細を閲覧できる"""
        self.client.login(username='staff', password='testpass123')
        response = self.client.get(reverse('book-detail', args=[self.draft.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Draft Book')

    def test_status_filter_combines_with_age_filter(self):
        """年齢絞り込みとステータス絞り込みが統合される"""
        Book.objects.create(title='Draft Age Book', age_min=3, age_max=6, status=Book.STATUS_DRAFT)
        response = self.client.get(reverse('book-list'), {'age': '4'})
        self.assertContains(response, 'Published Book')
        self.assertNotContains(response, 'Draft Book')
        self.assertNotContains(response, 'Draft Age Book')
        self.client.login(username='staff', password='testpass123')
        response = self.client.get(reverse('book-list'), {'age': '4'})
        self.assertContains(response, 'Published Book')
        self.assertContains(response, 'Draft Age Book')


class ReadingProgressViewTests(TestCase):
    """「続きから読む」: 保存・取得とアクセス制限の動作チェック"""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='progress1', password='testpass123')
        self.other = User.objects.create_user(username='progress2', password='testpass123')
        self.book = Book.objects.create(title='Progress Book', age_min=2, age_max=5, status=Book.STATUS_PUBLISHED)
        Page.objects.create(book=self.book, page_no=1, text_en='Page One')
        Page.objects.create(book=self.book, page_no=2, text_en='Page Two')
        Page.objects.create(book=self.book, page_no=3, text_en='Page Three')

    def test_progress_update_requires_login(self):
        """未ログインの進捗保存POSTはログイン画面へリダイレクトする"""
        url = reverse('progress-update', args=[self.book.pk])
        response = self.client.post(url, {'last_page_no': 2})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
        self.assertEqual(ReadingProgress.objects.count(), 0)

    def test_progress_detail_requires_login(self):
        """未ログインの進捗取得GETはログイン画面へリダイレクトする"""
        response = self.client.get(reverse('progress-detail', args=[self.book.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_progress_update_creates_record(self):
        """ログイン時は進捗が保存される"""
        self.client.login(username='progress1', password='testpass123')
        response = self.client.post(reverse('progress-update', args=[self.book.pk]), {'last_page_no': 2})
        self.assertEqual(response.status_code, 302)
        progress = ReadingProgress.objects.get(user=self.user, book=self.book)
        self.assertEqual(progress.last_page_no, 2)

    def test_progress_update_does_not_duplicate(self):
        """update_or_createにより1ユーザー1絵本1レコードを保つ"""
        self.client.login(username='progress1', password='testpass123')
        url = reverse('progress-update', args=[self.book.pk])
        self.client.post(url, {'last_page_no': 1})
        self.client.post(url, {'last_page_no': 3})
        self.assertEqual(ReadingProgress.objects.filter(user=self.user, book=self.book).count(), 1)
        self.assertEqual(ReadingProgress.objects.get(user=self.user, book=self.book).last_page_no, 3)

    def test_progress_update_invalid_page_falls_back_to_first(self):
        """不正値は1ページ目として保存される"""
        self.client.login(username='progress1', password='testpass123')
        self.client.post(reverse('progress-update', args=[self.book.pk]), {'last_page_no': 'abc'})
        self.assertEqual(ReadingProgress.objects.get(user=self.user, book=self.book).last_page_no, 1)
        self.client.post(reverse('progress-update', args=[self.book.pk]), {'last_page_no': '-5'})
        self.assertEqual(ReadingProgress.objects.get(user=self.user, book=self.book).last_page_no, 1)

    def test_progress_detail_returns_saved_page(self):
        """取得APIは保存済みの最終ページ番号を返す"""
        ReadingProgress.objects.create(user=self.user, book=self.book, last_page_no=3)
        self.client.login(username='progress1', password='testpass123')
        response = self.client.get(reverse('progress-detail', args=[self.book.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'book_id': self.book.pk, 'last_page_no': 3})

    def test_progress_detail_defaults_to_first_page(self):
        """未保存の場合は1ページ目を返す"""
        self.client.login(username='progress1', password='testpass123')
        response = self.client.get(reverse('progress-detail', args=[self.book.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['last_page_no'], 1)

    def test_progress_is_per_user(self):
        """進捗はユーザーごとに分離される"""
        ReadingProgress.objects.create(user=self.other, book=self.book, last_page_no=3)
        self.client.login(username='progress1', password='testpass123')
        response = self.client.get(reverse('progress-detail', args=[self.book.pk]))
        self.assertEqual(response.json()['last_page_no'], 1)

    def test_book_detail_saves_progress_for_logged_in_user(self):
        """詳細ページ表示時に開いているページが保存される"""
        self.client.login(username='progress1', password='testpass123')
        response = self.client.get(reverse('book-detail', args=[self.book.pk]), {'p': '2'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ReadingProgress.objects.get(user=self.user, book=self.book).last_page_no, 2)

    def test_book_detail_does_not_save_for_anonymous(self):
        """未ログインの詳細表示では進捗レコードを作らない"""
        response = self.client.get(reverse('book-detail', args=[self.book.pk]), {'p': '2'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ReadingProgress.objects.count(), 0)


class ResumeBannerTests(TestCase):
    """#52「続きから読む」導線: 一覧・詳細の表示チェック"""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='resume1', password='testpass123')
        self.book = Book.objects.create(title='Resume Book', age_min=2, age_max=5, status=Book.STATUS_PUBLISHED)
        Page.objects.create(book=self.book, page_no=1, text_en='Page One')
        Page.objects.create(book=self.book, page_no=2, text_en='Page Two')
        Page.objects.create(book=self.book, page_no=3, text_en='Page Three')

    def test_detail_shows_resume_banner_when_saved_page_differs(self):
        """保存p.3で?p=1を開くと?p=3への再開バナーが出る"""
        ReadingProgress.objects.create(user=self.user, book=self.book, last_page_no=3)
        self.client.login(username='resume1', password='testpass123')
        response = self.client.get(reverse('book-detail', args=[self.book.pk]), {'p': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'つづきから読む')
        self.assertContains(response, '?p=3')

    def test_detail_hides_resume_banner_when_same_page(self):
        """保存ページと開いているページが同じならバナーは出ない"""
        ReadingProgress.objects.create(user=self.user, book=self.book, last_page_no=2)
        self.client.login(username='resume1', password='testpass123')
        response = self.client.get(reverse('book-detail', args=[self.book.pk]), {'p': '2'})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'つづきから読む')

    def test_detail_hides_resume_banner_without_progress(self):
        """進捗がなければバナーは出ない"""
        self.client.login(username='resume1', password='testpass123')
        response = self.client.get(reverse('book-detail', args=[self.book.pk]), {'p': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'つづきから読む')

    def test_detail_hides_resume_banner_for_anonymous(self):
        """未ログインではバナーは出ない"""
        response = self.client.get(reverse('book-detail', args=[self.book.pk]), {'p': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'つづきから読む')

    def test_list_shows_resume_button_when_progress_exists(self):
        """一覧では進捗がある場合のみ再開ボタンが出て保存ページへ遷移できる"""
        ReadingProgress.objects.create(user=self.user, book=self.book, last_page_no=3)
        self.client.login(username='resume1', password='testpass123')
        response = self.client.get(reverse('book-list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'つづきから読む')
        self.assertContains(response, f'/books/{self.book.pk}/?p=3')

    def test_list_hides_resume_button_without_progress(self):
        """一覧では進捗がなければ再開ボタンは出ない"""
        self.client.login(username='resume1', password='testpass123')
        response = self.client.get(reverse('book-list'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'つづきから読む')


class FavoriteViewTests(TestCase):
    """お気に入り登録・解除・一覧取得とアクセス制限の動作チェック"""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='favuser', password='testpass123')
        self.other = User.objects.create_user(username='favother', password='testpass123')
        self.book = Book.objects.create(title='Fav Book', age_min=2, age_max=5, status=Book.STATUS_PUBLISHED)
        self.other_book = Book.objects.create(title='Other Fav Book', age_min=1, age_max=3, status=Book.STATUS_PUBLISHED)

    def test_favorite_add_requires_login(self):
        """未ログインの登録POSTはログイン画面へリダイレクトする"""
        url = reverse('favorite-add', args=[self.book.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
        self.assertEqual(Favorite.objects.count(), 0)

    def test_favorite_remove_requires_login(self):
        url = reverse('favorite-remove', args=[self.book.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_favorite_list_requires_login(self):
        response = self.client.get(reverse('favorite-list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_favorite_toggle_requires_login(self):
        url = reverse('favorite-toggle', args=[self.book.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_favorite_add_creates_favorite(self):
        """ログイン時はお気に入り登録できる"""
        self.client.login(username='favuser', password='testpass123')
        response = self.client.post(reverse('favorite-add', args=[self.book.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Favorite.objects.filter(user=self.user, book=self.book).exists())

    def test_favorite_add_is_idempotent(self):
        """重複登録しても1レコードのまま（get_or_create + UniqueConstraint）"""
        self.client.login(username='favuser', password='testpass123')
        url = reverse('favorite-add', args=[self.book.pk])
        self.client.post(url)
        self.client.post(url)
        self.assertEqual(Favorite.objects.filter(user=self.user, book=self.book).count(), 1)

    def test_favorite_remove_deletes_favorite(self):
        """ログイン時はお気に入り解除できる"""
        Favorite.objects.create(user=self.user, book=self.book)
        self.client.login(username='favuser', password='testpass123')
        response = self.client.post(reverse('favorite-remove', args=[self.book.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Favorite.objects.filter(user=self.user, book=self.book).exists())

    def test_favorite_remove_via_delete(self):
        """DELETEでも解除できる"""
        Favorite.objects.create(user=self.user, book=self.book)
        self.client.login(username='favuser', password='testpass123')
        response = self.client.delete(reverse('favorite-remove', args=[self.book.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Favorite.objects.filter(user=self.user, book=self.book).exists())

    def test_favorite_toggle_add_and_remove(self):
        """トグルは登録→解除を交互に行う"""
        self.client.login(username='favuser', password='testpass123')
        url = reverse('favorite-toggle', args=[self.book.pk])
        self.client.post(url)
        self.assertEqual(Favorite.objects.count(), 1)
        self.client.post(url)
        self.assertEqual(Favorite.objects.count(), 0)

    def test_favorite_list_shows_only_own_favorites(self):
        """一覧はログインユーザー自身の分だけ表示する"""
        Favorite.objects.create(user=self.user, book=self.book)
        Favorite.objects.create(user=self.other, book=self.other_book)
        self.client.login(username='favuser', password='testpass123')
        response = self.client.get(reverse('favorite-list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Fav Book')
        self.assertNotContains(response, 'Other Fav Book')


class FavoriteUITests(TestCase):
    """#51 お気に入りUI: 登録/解除の切替表示と一覧導線のチェック"""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='favui', password='testpass123')
        self.book = Book.objects.create(title='Fav UI Book', age_min=2, age_max=5, status=Book.STATUS_PUBLISHED)
        Page.objects.create(book=self.book, page_no=1, text_en='Page One')

    def test_detail_shows_register_button_when_not_favorited(self):
        """未登録なら「おきにいりする」と出る"""
        self.client.login(username='favui', password='testpass123')
        response = self.client.get(reverse('book-detail', args=[self.book.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'おきにいりする')
        self.assertNotContains(response, 'おきにいりしているよ')

    def test_detail_shows_registered_button_when_favorited(self):
        """登録済みなら「おきにいりしているよ」と出る"""
        Favorite.objects.create(user=self.user, book=self.book)
        self.client.login(username='favui', password='testpass123')
        response = self.client.get(reverse('book-detail', args=[self.book.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'おきにいりしているよ')
        self.assertNotContains(response, 'おきにいりする')

    def test_detail_login_prompt_for_anonymous(self):
        """未ログインの詳細ではボタンではなくログイン誘導が出る"""
        response = self.client.get(reverse('book-detail', args=[self.book.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ログインするとおきにいり')
        self.assertNotContains(response, 'おきにいりする')
        self.assertNotContains(response, 'おきにいりしているよ')

    def test_list_shows_favorite_buttons_when_logged_in(self):
        """一覧ではログイン時に登録ボタンと一覧への導線が出る"""
        self.client.login(username='favui', password='testpass123')
        response = self.client.get(reverse('book-list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'おきにいり')
        self.assertContains(response, reverse('favorite-list'))

    def test_list_shows_registered_state(self):
        """一覧では登録済みの本に「おきにいりちゅう」と出る"""
        Favorite.objects.create(user=self.user, book=self.book)
        self.client.login(username='favui', password='testpass123')
        response = self.client.get(reverse('book-list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'おきにいりちゅう')

    def test_list_hides_favorite_buttons_for_anonymous(self):
        """一覧では未ログイン時にお気に入りボタンは出ない"""
        response = self.client.get(reverse('book-list'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'おきにいり')


class AuthFlowTests(TestCase):
    """サインアップ〜ログイン〜ログアウトとアクセス制限の一通りの動作チェック"""

    def setUp(self):
        User = get_user_model()
        self.User = User
        self.user = User.objects.create_user(username='authuser', password='testpass123')
        self.book = Book.objects.create(title='Auth Book', age_min=2, age_max=5, status=Book.STATUS_PUBLISHED)

    def test_signup_creates_user_and_logs_in(self):
        """POST /accounts/signup/ でユーザーが作成されログイン状態になる"""
        response = self.client.post(reverse('signup'), {
            'username': 'newuser',
            'password1': 'strongpass123',
            'password2': 'strongpass123',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('book-list'))
        self.assertTrue(self.User.objects.filter(username='newuser').exists())
        # サインアップ直後はログイン済みとして扱われる
        response = self.client.get(reverse('book-list'))
        self.assertTrue(response.context['user'].is_authenticated)

    def test_signup_page_returns_200(self):
        response = self.client.get(reverse('signup'))
        self.assertEqual(response.status_code, 200)

    def test_login_works(self):
        """POST /accounts/login/ でログインできる"""
        response = self.client.post(reverse('login'), {
            'username': 'authuser',
            'password': 'testpass123',
        })
        self.assertEqual(response.status_code, 302)
        response = self.client.get(reverse('book-list'))
        self.assertTrue(response.context['user'].is_authenticated)

    def test_login_page_returns_200(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)

    def test_logout_works(self):
        """POST /accounts/logout/ でログアウトできる"""
        self.client.login(username='authuser', password='testpass123')
        response = self.client.post(reverse('logout'))
        self.assertEqual(response.status_code, 302)
        response = self.client.get(reverse('book-list'))
        self.assertFalse(response.context['user'].is_authenticated)

    def test_favorite_requires_login(self):
        """未ログインでお気に入りPOSTはログイン画面へリダイレクトする"""
        url = reverse('favorite-toggle', args=[self.book.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_favorite_toggle_authenticated(self):
        """ログイン時はお気に入り登録/解除がトグル動作する"""
        self.client.login(username='authuser', password='testpass123')
        url = reverse('favorite-toggle', args=[self.book.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Favorite.objects.count(), 1)
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Favorite.objects.count(), 0)

    def test_progress_requires_login(self):
        """未ログインで読書進捗POSTはログイン画面へリダイレクトする"""
        url = reverse('progress-update', args=[self.book.pk])
        response = self.client.post(url, {'last_page_no': 2})
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_progress_update_authenticated(self):
        """ログイン時は読書進捗が保存・更新される"""
        self.client.login(username='authuser', password='testpass123')
        url = reverse('progress-update', args=[self.book.pk])
        response = self.client.post(url, {'last_page_no': 2})
        self.assertEqual(response.status_code, 302)
        progress = ReadingProgress.objects.get(user=self.user, book=self.book)
        self.assertEqual(progress.last_page_no, 2)
        response = self.client.post(url, {'last_page_no': 5})
        progress.refresh_from_db()
        self.assertEqual(progress.last_page_no, 5)
        self.assertEqual(ReadingProgress.objects.count(), 1)




class BookBulkEditTests(TestCase):
    """一括更新API: 正常更新・ロールバック・権限の動作チェック"""

    GIF = (
        b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00'
        b'\xff\xff\xff!\xf9\x04\x00\x00\x00\x00\x00,\x00\x00\x00\x00'
        b'\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
    )

    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(shutil.rmtree, self.media_root, True)
        User = get_user_model()
        self.staff = User.objects.create_user(username='bulkstaff', password='testpass123', is_staff=True)
        self.user = User.objects.create_user(username='bulkuser', password='testpass123')
        self.book = Book.objects.create(
            title='Bulk Book', age_min=2, age_max=5, status=Book.STATUS_DRAFT)
        self.page1 = Page.objects.create(book=self.book, page_no=1, text_en='One', text_ja='いち')
        self.page2 = Page.objects.create(book=self.book, page_no=2, text_en='Two', text_ja='に')
        self.url = reverse('book-bulk-edit', args=[self.book.pk])

    def post_json(self, payload):
        return self.client.post(self.url, data=json.dumps(payload), content_type='application/json')

    def test_staff_valid_bulk_update(self):
        """スタッフが正しいデータで一括更新するとDBが更新される"""
        self.client.login(username='bulkstaff', password='testpass123')
        response = self.post_json({
            'book': {'title': 'Bulk Updated', 'age_min': 3, 'age_max': 6, 'status': 'published'},
            'pages': [
                {'page_no': 1, 'text_en': 'One Updated', 'text_ja': 'いち更新'},
                {'page_no': 2, 'text_en': 'Two', 'audio_url': 'https://example.com/a.mp3'},
                {'page_no': 3, 'text_en': 'Three New', 'text_ja': 'さん'},
            ],
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['book_id'], self.book.pk)
        self.assertEqual(sorted(data['updated_pages']), [1, 2])
        self.assertEqual(data['created_pages'], [3])
        self.book.refresh_from_db()
        self.assertEqual((self.book.title, self.book.age_min, self.book.age_max, self.book.status),
                         ('Bulk Updated', 3, 6, Book.STATUS_PUBLISHED))
        self.assertEqual(Page.objects.get(book=self.book, page_no=1).text_en, 'One Updated')
        self.assertEqual(Page.objects.get(book=self.book, page_no=2).audio_url, 'https://example.com/a.mp3')
        self.assertEqual(Page.objects.filter(book=self.book).count(), 3)

    def test_validation_error_rolls_back_everything(self):
        """不整合があれば一部も含めて更新されず400を返す"""
        self.client.login(username='bulkstaff', password='testpass123')
        response = self.post_json({
            'book': {'title': 'Should Not Save'},
            'pages': [
                {'page_no': 1, 'text_en': 'Should Not Save Either'},
                {'page_no': 1, 'text_en': 'Duplicate page_no'},
            ],
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('errors', response.json())
        self.book.refresh_from_db()
        self.assertEqual(self.book.title, 'Bulk Book')
        self.assertEqual(Page.objects.get(pk=self.page1.pk).text_en, 'One')
        self.assertEqual(Page.objects.filter(book=self.book).count(), 2)

    def test_invalid_age_range_rolls_back(self):
        """age_min > age_max は検証エラーとなり何も更新されない"""
        self.client.login(username='bulkstaff', password='testpass123')
        response = self.post_json({
            'book': {'age_min': 6, 'age_max': 3},
            'pages': [{'page_no': 2, 'text_en': 'Should Not Save'}],
        })
        self.assertEqual(response.status_code, 400)
        self.book.refresh_from_db()
        self.assertEqual((self.book.age_min, self.book.age_max), (2, 5))
        self.assertEqual(Page.objects.get(pk=self.page2.pk).text_en, 'Two')

    def test_anonymous_returns_401(self):
        """未ログインは401になる"""
        response = self.post_json({'book': {'title': 'Nope'}})
        self.assertEqual(response.status_code, 401)
        self.book.refresh_from_db()
        self.assertEqual(self.book.title, 'Bulk Book')

    def test_general_user_returns_403(self):
        """一般ユーザーは403になる"""
        self.client.login(username='bulkuser', password='testpass123')
        response = self.post_json({'book': {'title': 'Nope'}})
        self.assertEqual(response.status_code, 403)
        self.book.refresh_from_db()
        self.assertEqual(self.book.title, 'Bulk Book')

    def test_image_update_via_multipart(self):
        """multipartでページ画像を一括更新できる"""
        self.client.login(username='bulkstaff', password='testpass123')
        response = self.client.post(self.url, {
            'payload': json.dumps({'pages': [{'page_no': 1, 'text_en': 'One'}]}),
            'page_image_1': SimpleUploadedFile('p1.gif', self.GIF, 'image/gif'),
        })
        self.assertEqual(response.status_code, 200)
        page = Page.objects.get(pk=self.page1.pk)
        self.assertTrue(page.image.name)
        with page.image.open('rb') as f:
            self.assertEqual(f.read(), self.GIF)

    def test_invalid_image_returns_400_without_update(self):
        """画像として読めないファイルは400となり何も更新されない"""
        self.client.login(username='bulkstaff', password='testpass123')
        response = self.client.post(self.url, {
            'payload': json.dumps({'pages': [{'page_no': 1, 'text_en': 'Should Not Save'}]}),
            'page_image_1': SimpleUploadedFile('p1.txt', b'not an image', 'text/plain'),
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Page.objects.get(pk=self.page1.pk).text_en, 'One')


class BookCopyTests(TestCase):
    """絵本の複製: Book+Pageの作成・タイトル・status・独立性・画像複製"""

    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(shutil.rmtree, self.media_root, True)
        User = get_user_model()
        self.staff = User.objects.create_user(username='copystaff', password='testpass123', is_staff=True)
        self.user = User.objects.create_user(username='copyuser', password='testpass123')
        self.book = Book.objects.create(
            title='Copy Me', age_min=2, age_max=5,
            status=Book.STATUS_PUBLISHED, description='desc', description_ja='せつめい')
        Page.objects.create(book=self.book, page_no=1, text_en='One', text_ja='いち')
        Page.objects.create(book=self.book, page_no=2, text_en='Two', text_ja='に')

    def test_copy_creates_new_book_and_pages(self):
        """コピー実行で新しいBookと全Pageが作成される"""
        new_book = copy_book(self.book)
        self.assertEqual(Book.objects.count(), 2)
        self.assertEqual(new_book.pages.count(), 2)
        self.assertEqual(
            list(new_book.pages.order_by('page_no').values_list('page_no', 'text_en', flat=False)),
            [(1, 'One'), (2, 'Two')])
        self.assertEqual(new_book.age_min, 2)
        self.assertEqual(new_book.description_ja, 'せつめい')

    def test_copy_title_and_status(self):
        """タイトル末尾に「（コピー）」、statusはdraftになる"""
        new_book = copy_book(self.book)
        self.assertEqual(new_book.title, 'Copy Me（コピー）')
        self.assertEqual(new_book.status, Book.STATUS_DRAFT)
        self.assertIsNone(new_book.published_at)

    def test_copy_is_independent(self):
        """元のBook/PageとIDが異なり独立している"""
        new_book = copy_book(self.book)
        self.assertNotEqual(new_book.pk, self.book.pk)
        old_page_ids = set(self.book.pages.values_list('pk', flat=True))
        new_page_ids = set(new_book.pages.values_list('pk', flat=True))
        self.assertTrue(new_page_ids)
        self.assertFalse(old_page_ids & new_page_ids)
        new_book.title = 'Changed'
        new_book.save()
        self.book.refresh_from_db()
        self.assertEqual(self.book.title, 'Copy Me')

    def test_copy_duplicates_images(self):
        """画像ファイルも複製され参照が分かれる"""
        gif = (
            b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xff\xff\xff!\xf9\x04\x00\x00\x00\x00\x00,\x00\x00\x00\x00'
            b'\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
        )
        book = Book.objects.create(title='Img Book', age_min=1, age_max=3)
        book.cover_image.save('cover.gif', SimpleUploadedFile('cover.gif', gif, 'image/gif'), save=True)
        page = Page.objects.create(book=book, page_no=1, text_en='Hi')
        page.image.save('p1.gif', SimpleUploadedFile('p1.gif', gif, 'image/gif'), save=True)
        new_book = copy_book(book)
        self.assertNotEqual(new_book.cover_image.name, book.cover_image.name)
        new_page = new_book.pages.get(page_no=1)
        self.assertNotEqual(new_page.image.name, page.image.name)
        with new_book.cover_image.open('rb') as f:
            self.assertEqual(f.read(), gif)
        with new_page.image.open('rb') as f:
            self.assertEqual(f.read(), gif)

    def test_copy_view_requires_staff(self):
        """複製APIはスタッフのみ実行できる"""
        url = reverse('book-copy', args=[self.book.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)
        self.client.login(username='copyuser', password='testpass123')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Book.objects.count(), 1)
        self.client.login(username='copystaff', password='testpass123')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Book.objects.count(), 2)
        copied = Book.objects.exclude(pk=self.book.pk).get()
        self.assertEqual(copied.title, 'Copy Me（コピー）')
        self.assertEqual(copied.status, Book.STATUS_DRAFT)

    def test_admin_action_duplicates_books(self):
        """Admin Actionから複製できる"""
        admin_user = get_user_model().objects.create_superuser(
            username='copyadmin', password='testpass123', email='a@example.com')
        self.client.force_login(admin_user)
        response = self.client.post(reverse('admin:books_book_changelist'), {
            'action': 'duplicate_books',
            '_selected_action': [str(self.book.pk)],
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Book.objects.count(), 2)
        copied = Book.objects.exclude(pk=self.book.pk).get()
        self.assertEqual(copied.title, 'Copy Me（コピー）')
        self.assertEqual(copied.status, Book.STATUS_DRAFT)
        self.assertEqual(copied.pages.count(), 2)


class StaffAdminUITests(TestCase):
    """#56 管理者向けUI: 下書きプレビュー・一括編集・複製の表示と権限制御"""

    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user(username='staffui', password='testpass123', is_staff=True)
        self.user = User.objects.create_user(username='normalui', password='testpass123')
        self.draft = Book.objects.create(title='Draft Preview Book', age_min=2, age_max=5, status=Book.STATUS_DRAFT)
        Page.objects.create(book=self.draft, page_no=1, text_en='Draft Page One')
        self.published = Book.objects.create(title='Published UI Book', age_min=2, age_max=5, status=Book.STATUS_PUBLISHED)
        Page.objects.create(book=self.published, page_no=1, text_en='Page One')

    def test_detail_staff_bar_for_staff_on_draft(self):
        """スタッフの下書き詳細にはプレビューバッジ・一括編集・複製が出る"""
        self.client.login(username='staffui', password='testpass123')
        response = self.client.get(reverse('book-detail', args=[self.draft.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '下書きプレビュー中')
        self.assertContains(response, reverse('book-bulk-edit-form', args=[self.draft.pk]))
        self.assertContains(response, reverse('book-copy', args=[self.draft.pk]))

    def test_detail_no_staff_bar_for_normal_user(self):
        """一般ユーザーの詳細にはスタッフUIが出ない"""
        self.client.login(username='normalui', password='testpass123')
        response = self.client.get(reverse('book-detail', args=[self.published.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '<div class="staff-bar">')
        self.assertNotContains(response, '複製する')
        self.assertNotContains(response, '一括編集')

    def test_bulk_edit_form_staff_200(self):
        """スタッフは一括編集画面を開ける"""
        self.client.login(username='staffui', password='testpass123')
        response = self.client.get(reverse('book-bulk-edit-form', args=[self.draft.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '一括編集')
        self.assertContains(response, reverse('book-bulk-edit', args=[self.draft.pk]))

    def test_bulk_edit_form_normal_user_redirected(self):
        """一般ユーザーは一括編集画面を開けない"""
        self.client.login(username='normalui', password='testpass123')
        response = self.client.get(reverse('book-bulk-edit-form', args=[self.published.pk]))
        self.assertEqual(response.status_code, 302)

    def test_bulk_edit_form_anonymous_redirected(self):
        """未ログインは一括編集画面を開けない"""
        response = self.client.get(reverse('book-bulk-edit-form', args=[self.published.pk]))
        self.assertEqual(response.status_code, 302)

    def test_list_draft_badge_for_staff_only(self):
        """一覧の下書きバッジはスタッフにだけ出る"""
        self.client.login(username='staffui', password='testpass123')
        response = self.client.get(reverse('book-list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '下書き</span>')
        self.client.login(username='normalui', password='testpass123')
        response = self.client.get(reverse('book-list'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '下書き</span>')
