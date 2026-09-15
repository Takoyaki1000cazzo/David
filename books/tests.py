from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from .models import Book, Page


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
