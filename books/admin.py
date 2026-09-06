from django.contrib import admin

from .models import Book, Page


class PageInline(admin.TabularInline):
    model = Page
    extra = 1
    fields = ('page_no', 'text_en', 'text_ja', 'image', 'audio_url')


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'age_min', 'age_max', 'created_at')
    list_filter = ('age_min', 'age_max')
    search_fields = ('title',)
    inlines = [PageInline]


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ('book', 'page_no', 'created_at')
    list_filter = ('book',)
