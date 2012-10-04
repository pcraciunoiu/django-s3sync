import datetime
import email
import mimetypes
import os
import time

import boto.exception
from boto.s3.connection import S3Connection

from django.conf import settings
from django.core.cache import get_cache


GZIP_CONTENT_TYPES = (
    'text/css',
    'application/javascript',
    'application/x-javascript',
    'text/javascript'
)


class ConfigMissingError(Exception):
    """Raise this when (AWS) settings are missing."""
    pass


def get_bucket_and_key(name):
    """Connect to S3 and grab bucket and key."""
    key,secret,host = get_aws_info()
    conn =  S3Connection(key,secret,host=host)
    try:
        bucket = conn.get_bucket(name)
    except boto.exception.S3ResponseError:
        bucket = conn.create_bucket(name)
    return bucket, boto.s3.key.Key(bucket)


def get_aws_info():
    if not hasattr(settings, 'AWS_ACCESS_KEY_ID') or \
        not hasattr(settings, 'AWS_SECRET_ACCESS_KEY'):
        raise ConfigMissingError
    host = getattr(settings,'AWS_S3_HOST','s3.amazonaws.com')
    key, secret = settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY
    return key, secret, host


def get_pending_key():
    return getattr(settings, 'BUCKET_UPLOADS_PENDING_KEY', 's3-pending')


def get_pending_delete_key():
    return getattr(settings, 'BUCKET_UPLOADS_PENDING_DELETE_KEY',
                    's3-pending-delete')


def get_s3sync_cache():
    return get_cache(getattr(settings, 'BUCKET_UPLOADS_CACHE_ALIAS',
                                        'default'))


def guess_mimetype(f):
    return mimetypes.guess_type(f)[0]


def upload_file_to_s3(file_key, filename, key, do_gzip=False,
                    do_expires=False, verbosity=0):
    """Details about params:
    * file_key is the relative path from media, e.g. media/folder/file.png
    * filename is the full path to the file, e.g.
        /var/www/site/media/folder/file.png
    """
    headers = {}
    content_type = guess_mimetype(filename)
    file_obj = open(filename, 'rb')
    if content_type:
        headers['Content-Type'] = content_type
    file_size = os.fstat(file_obj.fileno()).st_size
    filedata = file_obj.read()
    if do_gzip:
        # Gzipping only if file is large enough (>1K is recommended)
        # and only if file is a common text type (not a binary file)
        if (file_size > 1024 and content_type in GZIP_CONTENT_TYPES):
            filedata = compress_string(filedata)
            headers['Content-Encoding'] = 'gzip'
            gzip_file_size = len(filedata)
            if verbosity > 1:
                print "\tgzipped: %dk to %dk" % \
                    (file_size / 1024, gzip_file_size / 1024)
            file_size = gzip_file_size
    headers['Content-Length'] = str(file_size)
    if do_expires:
        # HTTP/1.0
        headers['Expires'] = '%s GMT' % (email.Utils.formatdate(
            time.mktime((datetime.datetime.now() +
                datetime.timedelta(days=365 * 2)).timetuple())))
        # HTTP/1.1
        headers['Cache-Control'] = 'max-age %d' % (3600 * 24 * 365 * 2)

    try:
        key.name = file_key
        key.set_contents_from_string(filedata, headers, replace=True)
        key.set_acl('public-read')
    finally:
        file_obj.close()


def compress_string(s):
    """Gzip a given string."""
    import gzip
    try:
        from cStringIO import StringIO
    except ImportError:
        from StringIO import StringIO
    zbuf = StringIO()
    zfile = gzip.GzipFile(mode='wb', compresslevel=6, fileobj=zbuf)
    zfile.write(s)
    zfile.close()
    return zbuf.getvalue()
