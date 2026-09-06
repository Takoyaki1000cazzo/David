from django.core.exceptions import ValidationError
from django.db import models


class Book(models.Model):
    title = models.CharField(max_length=200)
    cover_image = models.ImageField(upload_to='covers/', blank=True, null=True)
    age_min = models.PositiveSmallIntegerField()
    age_max = models.PositiveSmallIntegerField()
    description = models.TextField(blank=True)
    description_ja = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} ({self.age_min}-{self.age_max})'

    def clean(self):
        if self.age_min is not None and self.age_max is not None:
            if self.age_min > self.age_max:
                raise ValidationError('age_min must be <= age_max')


class Page(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='pages')
    page_no = models.PositiveIntegerField()
    text_en = models.TextField()
    text_ja = models.TextField(blank=True)
    image = models.ImageField(upload_to='pages/', blank=True, null=True)
    audio_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['page_no']
        constraints = [
            models.UniqueConstraint(fields=['book', 'page_no'], name='unique_book_page_no'),
        ]

    def __str__(self):
        return f'{self.book.title} p.{self.page_no}'
