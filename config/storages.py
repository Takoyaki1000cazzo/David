"""本番・CI両対応の静的ファイルストレージ。

WhiteNoiseのManifest保管を継承しつつ、`manifest_strict = False` で
マニフェスト不在時（CIなどcollectstatic未実行環境）も
元のファイル名でフォールバックしてValueErrorにしない。
"""
from whitenoise.storage import CompressedManifestStaticFilesStorage


class ForgivingManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    manifest_strict = False
