from django.contrib import admin

from .models import Book, Favorite, Page
from .services import copy_book


@admin.action(description='選択した絵本を複製する（タイトルに「（コピー）」・下書き・画像複製）')
def duplicate_books(modeladmin, request, queryset):
    count = 0
    for book in queryset.prefetch_related('pages'):
        copy_book(book)
        count += 1
    modeladmin.message_user(request, f'{count}件の絵本を複製しました（下書きとして保存）。')


class PageInline(admin.TabularInline):
    model = Page
    extra = 1
    fields = ('page_no', 'text_en', 'text_ja', 'image', 'audio_url')


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'age_min', 'age_max', 'created_at')
    list_filter = ('status', 'age_min', 'age_max')
    search_fields = ('title',)
    inlines = [PageInline]
    actions = [duplicate_books]


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ('book', 'page_no', 'created_at')
    list_filter = ('book',)


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'book', 'created_at')
    list_filter = ('book',)
