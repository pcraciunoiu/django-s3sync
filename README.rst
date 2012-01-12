Django S3 Sync
==============

Keep your static and user-uploaded media in sync between your local machine and Amazon S3 buckets. Features:

* Use separate buckets for user-uploaded media VS static media
* Run a management command periodically to keep your user-uploaded media in sync.
* Fall back to local ``MEDIA_URL`` links for files that have not yet been uploaded to S3 (uses any cache backend to store this list).
* Automatically link to files on S3 when they have been uploaded.

Limitations
~~~~~~~~~~~

* This app only works with Django's ``FileSystemStorage`` backend. You are welcome to file a pull request to fix this limitation, feel free to ask me for help :)
* Using symlinks (``ln -s``) in your static media has not been tested, and is assumed not to work.

Installation
------------

#. Step 1::

    pip install -e git://github.com/pcraciunoiu/django-s3sync#egg=django-s3sync

#. Add ``s3sync`` to your installed apps::

    INSTALLED_APPS = (
        # ...
        's3sync',
        # ...
    )

#. Set s3sync's ``S3PendingStorage`` backend as the default::

    DEFAULT_FILE_STORAGE = 's3sync.storage.S3PendingStorage'

#. Provide these settings, all required (for now)::

    MEDIA_ROOT = '/full/path/to/your/media'
    AWS_ACCESS_KEY_ID = 'your-amazon-access-key-id'
    AWS_SECRET_ACCESS_KEY = 'your-amazon-secret-access-key'
    BUCKET_UPLOADS = 's3-2.sowink.net'
    BUCKET_UPLOADS_URL = '//s3-2.sowink.net/media/'

#. Run this on a cron::

    # Be sure to use your media prefix here.
    python manage.py s3sync_pending --prefix=media

#. To sync your static media, see `cron.py <https://github.com/pcraciunoiu/django-s3sync/tree/master/example/cron.py>`_


Already using a custom File storage backend?
--------------------------------------------

Extend s3sync's storage::
    from s3sync.storage import S3PendingStorage
     
    class YourCustomStorage(S3PendingStorage):
        # Override with your storage methods here.
        pass


Usage
-----

python manage.py s3sync_media
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Command options are::

  -b BUCKET, --bucket=BUCKET
                        The name of the Amazon bucket you are uploading to.
  -p PREFIX, --prefix=PREFIX
                        The prefix to prepend to the path on S3.
  -d DIRECTORY, --dir=DIRECTORY
                        The root directory to use instead of your MEDIA_ROOT
  --gzip                Enables gzipping CSS and Javascript files.
  --expires             Enables setting a far future expires header.
  --force               Skip the file mtime check to force upload of all
                        files.
  --remove-missing
                        Remove any existing keys from the bucket that are not
                        present in your local. DANGEROUS!
  --exclude-list        Override default directory and file exclusion
                        filters. (enter as comma separated line)
  --dry-run
                        Do A dry-run to show what files would be affected.


python manage.py s3sync_pending
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Required settings: ``BUCKET_UPLOADS``

Command options are::

  -p PREFIX, --prefix=PREFIX
                        The prefix to prepend to the path on S3.
  -d DIRECTORY, --dir=DIRECTORY
                        The root directory to use instead of your MEDIA_ROOT
  --dry-run
                        Do a dry-run to show what files would be affected.

s3sync.storage.S3PendingStorage
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Required settings: ``BUCKET_UPLOADS_URL``


Full List of Settings
~~~~~~~~~~~~~~~~~~~~~

``BUCKET_UPLOADS``
  Name of your upload bucket. Usually 'something.yourdomain.com'

``BUCKET_UPLOADS_URL``
  URL to your bucket, including the prefix.

``BUCKET_UPLOADS_CACHE_ALIAS``
  Which cache backend to use from `settings.CACHES <https://docs.djangoproject.com/en/dev/ref/settings/#std:setting-CACHES>`_

``BUCKET_UPLOADS_PENDING_KEY``
  Cache key to use for storing the list of pending files to be uploaded to S3.

``BUCKET_UPLOADS_PENDING_DELETE_KEY``
  Cache key to use for storing the list of pending files to be removed from S3.

Contributing
============
If you'd like to fix a bug, add a feature, etc

#. Start by opening an issue.
    Be explicit so that project collaborators can understand and reproduce the
    issue, or decide whether the feature falls within the project's goals.
    Code examples can be useful, too.

#. File a pull request.
    You may write a prototype or suggested fix.

#. Check your code for errors, complaints.
    Use `check.py <https://github.com/jbalogh/check>`_

#. Write and run tests.
    Write your own test showing the issue has been resolved, or the feature
    works as intended.

Running Tests
=============

*TODO*: write tests.

To run the tests::

    python manage.py test s3sync
