from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from .models import Book, Favorite, Page, ReadingProgress


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
        book = Book.objects.create(title='Test Book', age_min=2, age_max=5)
        response = self.client.get(reverse('book-list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Book')

    def test_book_list_with_empty_cover(self):
        """表紙画像が空でも一覧画面が表示される"""
        book = Book.objects.create(title='Test Book', age_min=2, age_max=5)
        response = self.client.get(reverse('book-list'))
        self.assertEqual(response.status_code, 200)

    def test_book_detail_with_empty_fields(self):
        """説明文・表紙が空でも詳細画面が表示される"""
        book = Book.objects.create(title='Test Book', age_min=2, age_max=5)
        Page.objects.create(book=book, page_no=1, text_en='Hello')
        response = self.client.get(reverse('book-detail', args=[book.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Book')

    def test_book_detail_with_empty_page_image(self):
        """ページ画像が空でも詳細画面が表示される"""
        book = Book.objects.create(title='Test Book', age_min=2, age_max=5)
        Page.objects.create(book=book, page_no=1, text_en='Hello', text_ja='こんにちは')
        response = self.client.get(reverse('book-detail', args=[book.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hello')


class BookDetailPageValidationTests(TestCase):
    """D6: ?p= に不正値が渡されてもエラーにならず安全に動くこと"""

    def setUp(self):
        self.book = Book.objects.create(title='Test Book', age_min=2, age_max=5)
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
        self.book = Book.objects.create(title='Next Book', age_min=2, age_max=5)
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
        empty = Book.objects.create(title='Empty', age_min=1, age_max=2)
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
        Book.objects.create(title='List Check Book', age_min=3, age_max=6)
        response = self.client.get(reverse('book-list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'List Check Book')

    def test_book_detail_returns_200(self):
        """詳細ページ `/books/<id>/` は HTTP 200 を返す"""
        book = Book.objects.create(title='Detail Check Book', age_min=3, age_max=6)
        Page.objects.create(book=book, page_no=1, text_en='Hello')
        response = self.client.get(reverse('book-detail', args=[book.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Detail Check Book')

    def test_book_list_age_filter(self):
        """`/?age=4` は対象(3-6歳)のみ表示し対象外(1-2歳)を表示しない"""
        Book.objects.create(title='Target Age Book', age_min=3, age_max=6)
        Book.objects.create(title='Out Of Range Book', age_min=1, age_max=2)
        response = self.client.get(reverse('book-list'), {'age': '4'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Target Age Book')
        self.assertNotContains(response, 'Out Of Range Book')


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
