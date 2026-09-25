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


class ReadingProgressViewTests(TestCase):
    """「続きから読む」: 保存・取得とアクセス制限の動作チェック"""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='progress1', password='testpass123')
        self.other = User.objects.create_user(username='progress2', password='testpass123')
        self.book = Book.objects.create(title='Progress Book', age_min=2, age_max=5)
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


class FavoriteViewTests(TestCase):
    """お気に入り登録・解除・一覧取得とアクセス制限の動作チェック"""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='favuser', password='testpass123')
        self.other = User.objects.create_user(username='favother', password='testpass123')
        self.book = Book.objects.create(title='Fav Book', age_min=2, age_max=5)
        self.other_book = Book.objects.create(title='Other Fav Book', age_min=1, age_max=3)

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


class AuthFlowTests(TestCase):
    """サインアップ〜ログイン〜ログアウトとアクセス制限の一通りの動作チェック"""

    def setUp(self):
        User = get_user_model()
        self.User = User
        self.user = User.objects.create_user(username='authuser', password='testpass123')
        self.book = Book.objects.create(title='Auth Book', age_min=2, age_max=5)

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
