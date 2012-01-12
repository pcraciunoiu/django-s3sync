from django.conf import settings
from django.core.files.storage import FileSystemStorage as DjangoStorage

from s3sync.utils import (get_pending_key, get_pending_delete_key,
    get_s3sync_cache)


deleting_key = get_pending_delete_key()
pending_key = get_pending_key()
cache = get_s3sync_cache()
is_production = getattr(settings, 'PRODUCTION', False)


class S3PendingStorage(DjangoStorage):
    """Subclass Django's file system storage to queue new files as pending
    to a cache key, for later S3 upload using an s3sync cron."""

    def delete(self, name):
        """Remove files that were pending, or mark non-pending for deletion."""
        super(S3PendingStorage, self).delete(name)
        if not is_production:
            return
        deleting = cache.get(deleting_key, [])
        pending = cache.get(pending_key, [])
        # File was pending? Ok, remove it from upload queue.
        if name in pending:
            cache.delete(name)
            del pending[pending.index(name)]
        else:  # otherwise, mark it for deletion
            deleting.append(name)
        cache.set(deleting_key, deleting)
        cache.set(pending_key, pending)

    def save(self, name, content):
        new_name = super(S3PendingStorage, self).save(name, content)
        if not is_production:
            return new_name
        cache.set(new_name, True)
        pending = cache.get(pending_key, [])
        if not new_name in pending:
            pending.append(new_name)
        cache.set(pending_key, pending)
        return new_name

    def url(self, name):
        url = super(S3PendingStorage, self).url(name)
        # Is this file pending? Return local URL.
        if cache.get(name) or not is_production:
            return url
        return settings.BUCKET_UPLOADS_URL + name
