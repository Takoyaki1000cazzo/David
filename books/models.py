from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB


def validate_image_file(value):
    """画像の形式とファイルサイズを検証する。adminフォームとfull_cleanの両方で効く。"""
    import os

    ext = os.path.splitext(value.name)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(f'画像形式は PNG/JPG/WebP にしてください（{ext} は不可）')
    if value.size and value.size > MAX_IMAGE_SIZE:
        raise ValidationError('画像サイズは5MB以下にしてください')


class Book(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_PUBLISHED = 'published'
    STATUS_CHOICES = [
        (STATUS_DRAFT, '下書き'),
        (STATUS_PUBLISHED, '公開'),
    ]

    title = models.CharField(max_length=200)
    cover_image = models.ImageField(
        upload_to='covers/', blank=True, null=True, validators=[validate_image_file])
    age_min = models.PositiveSmallIntegerField()
    age_max = models.PositiveSmallIntegerField()
    description = models.TextField(blank=True)
    description_ja = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    published_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                check=models.Q(age_min__lte=models.F('age_max')),
                name='age_min_lte_age_max',
            ),
        ]

    def __str__(self):
        return f'{self.title} ({self.age_min}-{self.age_max})'

    def clean(self):
        if self.age_min is not None and self.age_max is not None:
            if self.age_min > self.age_max:
                raise ValidationError('age_min must be <= age_max')
            for field, value in (('age_min', self.age_min), ('age_max', self.age_max)):
                if not 0 <= value <= 12:
                    raise ValidationError({field: '対象年齢は0〜12の範囲にしてください'})


class Page(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='pages')
    page_no = models.PositiveIntegerField()
    text_en = models.TextField()
    text_ja = models.TextField(blank=True)
    image = models.ImageField(
        upload_to='pages/', blank=True, null=True, validators=[validate_image_file])
    audio_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['page_no']
        constraints = [
            models.UniqueConstraint(fields=['book', 'page_no'], name='unique_book_page_no'),
        ]

    def clean(self):
        if not (self.text_en or '').strip():
            raise ValidationError({'text_en': '英文テキストは必須です'})

    def __str__(self):
        return f'{self.book.title} p.{self.page_no}'


class ReadingProgress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reading_progress')
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='reading_progress')
    last_page_no = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'book'], name='unique_user_book_progress'),
        ]

    def __str__(self):
        return f'{self.user} - {self.book.title} p.{self.last_page_no}'


class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='favorite_books')
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'book'], name='unique_user_book_favorite'),
        ]

    def __str__(self):
        return f'{self.user} ♥ {self.book.title}'
