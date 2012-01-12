from django.conf import settings
from django.core import management

# Simple cron app from https://github.com/jsocol/django-cronjobs
import cronjobs


@cronjobs.register
def upload_static_media_to_s3():
    # Sync assets, exclude uploads, etc.
    management.call_command('s3sync_media', verbosity=1, interactive=False,
        remove_missing=True,
        exclude_list=['.*', 'Thumbs.db', 'uploads*', 'less'],
        bucket=settings.BUCKET_ASSETS,
        prefix=settings.BUCKET_ASSETS_PREFIX)


@cronjobs.register
def upload_user_media_to_s3():
    # Sync assets, exclude uploads, etc.
    management.call_command('s3sync_media', verbosity=1, interactive=False,
        exclude_list=['.htaccess'], remove_missing=True,
        dir=settings.BUCKET_UPLOADS_PATH,
        bucket=settings.BUCKET_UPLOADS,
        prefix=settings.BUCKET_UPLOADS_PREFIX)
