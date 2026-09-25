"""絵本の複製ロジック。"""
import os
import uuid

from django.core.files.base import ContentFile
from django.db import transaction

COPY_SUFFIX = '（コピー）'


def _duplicate_image(source_field, upload_to):
    """画像ファイルを物理コピーし、(保存名, ContentFile) を返す。

    元ファイルが存在しない場合は None を返す（複製全体は継続する）。
    戻り値の保存名は元のパスと重ならない一意な名前になる。
    """
    if not source_field or not source_field.name:
        return None
    try:
        with source_field.open('rb') as f:
            content = ContentFile(f.read())
    except (FileNotFoundError, OSError, ValueError):
        return None
    ext = os.path.splitext(source_field.name)[1]
    return f'{upload_to}{uuid.uuid4().hex}{ext}', content


def copy_book(book):
    """Book と関連する全 Page を複製して新しい Book を返す。

    - タイトル末尾に「（コピー）」を付与する（max_length超過時は切り詰める）
    - status は draft、published_at はクリアする
    - 表紙・ページ画像はファイルを複製し新しい参照を設定する
    - お気に入り・読書進捗などのユーザー紐付けデータは複製しない
    """
    from .models import Book, Page

    max_title_length = Book._meta.get_field('title').max_length
    title = f'{book.title}{COPY_SUFFIX}'
    if len(title) > max_title_length:
        title = f'{book.title[:max_title_length - len(COPY_SUFFIX)]}{COPY_SUFFIX}'

    cover_data = _duplicate_image(book.cover_image, 'covers/')

    with transaction.atomic():
        new_book = Book(
            title=title,
            age_min=book.age_min,
            age_max=book.age_max,
            description=book.description,
            description_ja=book.description_ja,
            status=Book.STATUS_DRAFT,
            published_at=None,
        )
        if cover_data:
            name, content = cover_data
            new_book.cover_image.save(name, content, save=False)
        new_book.save()

        for page in book.pages.all().order_by('page_no'):
            image_data = _duplicate_image(page.image, 'pages/')
            new_page = Page(
                book=new_book,
                page_no=page.page_no,
                text_en=page.text_en,
                text_ja=page.text_ja,
                audio_url=page.audio_url,
            )
            if image_data:
                name, content = image_data
                new_page.image.save(name, content, save=False)
            new_page.save()

    return new_book
