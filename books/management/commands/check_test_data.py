"""開発用テストデータの検証コマンド（読み取り専用）。"""
import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from books.models import Book, Favorite, Page, ReadingProgress


class Command(BaseCommand):
    help = '開発用テストデータの件数・公開状態・画像有無を検証する'

    def handle(self, *args, **options):
        problems = []
        books = Book.objects.count()
        pages = Page.objects.count()
        drafts = Book.objects.exclude(status='published').count()
        self.stdout.write(f'books: {books} (draft: {drafts})')
        self.stdout.write(f'pages: {pages}')
        self.stdout.write(f'users: {User.objects.count()}')
        self.stdout.write(f'favorites: {Favorite.objects.count()}')
        self.stdout.write(f'progress: {ReadingProgress.objects.count()}')
        for b in Book.objects.all():
            if b.cover_image and not os.path.exists(b.cover_image.path):
                problems.append(f'missing cover: {b.pk} {b.title}')
        for p in Page.objects.all():
            if p.image and not os.path.exists(p.image.path):
                problems.append(f'missing image: book {p.book_id} p{p.page_no}')
        if problems:
            for m in problems:
                self.stderr.write(m)
            raise SystemExit(1)
        self.stdout.write('test data OK')
