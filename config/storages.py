"""本番・CI両対応の静的ファイルストレージ。

WhiteNoiseのManifest保管を継承しつつ、collectstatic未実行環境
（CIのtest等）でも `{% static %}` がValueErrorで落ちないよう、
ハッシュ解決失敗時は元のファイル名にフォールバックする。
`manifest_strict = False` だけでは `hashed_name()` のValueErrorを
防げないため、`hashed_name()` / `url()` を明示的に救済する。
"""
from whitenoise.storage import CompressedManifestStaticFilesStorage


class ForgivingManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    manifest_strict = False

    def hashed_name(self, name, content=None, filename=None):
        try:
            return super().hashed_name(name, content, filename)
        except ValueError:
            return name

    def url(self, name, force=False):
        try:
            return super().url(name, force)
        except ValueError:
            # Manifest解決に失敗したらハッシュ化せず素のURLを返す
            return super(
                CompressedManifestStaticFilesStorage, self
            ).url(name, force)
