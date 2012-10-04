INSTALLED_APPS += (
    's3sync',
    'redis_cache',
)

# This example is using redis as a cache backend
# https://github.com/sebleier/django-redis-cache
CACHES['s3-storage'] = {
    'BACKEND': 'redis_cache.RedisCache',
    'LOCATION': 'localhost:1234',
    'TIMEOUT': 3600 * 24 * 30,  # =30 days, in seconds
    'OPTIONS': {
        'DB': 2,
    }
}

MEDIA_ROOT = '/var/www/site/media'
# Sync media
BUCKET_ASSETS = 'example-static-bucket.yourdomain.com'
BUCKET_ASSETS_PREFIX = 'media'
BUCKET_UPLOADS = 'example-upload-bucket.yourdomain.com'
BUCKET_UPLOADS_PREFIX = 'media/uploads'
BUCKET_UPLOADS_PATH = MEDIA_ROOT + '/uploads'
BUCKET_UPLOADS_URL = '//example-upload-bucket.yourdomain.com/media/'
BUCKET_UPLOADS_CACHE_ALIAS = 's3-storage'
BUCKET_UPLOADS_PENDING_KEY = 's3-pending'
BUCKET_UPLOADS_PENDING_DELETE_KEY = 's3-pending-delete'

# S3 Host/Region
# To connect to your S3 host region, you may want to set this to avoid a BrokenPipeException
# e.g. for EU, 's3-eu-west-1.amazonaws.com'
AWS_S3_HOST = 's3.amazonaws.com'
