from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

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
