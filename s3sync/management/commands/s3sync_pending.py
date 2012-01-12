"""
Upload pending Media to S3
==========================

Django command that retrieves all files from your chosen cache backend
and uploads them to S3. Useful to run as a cron to sync files periodically,
in conjunction with the storage backend for URLs.

Note: This script requires the Python boto library and valid Amazon Web
Services API keys.

Required settings.py variables:
AWS_ACCESS_KEY_ID = ''
AWS_SECRET_ACCESS_KEY = ''
BUCKET_UPLOADS = 'bucket-name.yourdomain.com'

Command options are:
  -p PREFIX, --prefix=PREFIX
                        The prefix to prepend to the path on S3.
  -d DIRECTORY, --dir=DIRECTORY
                        The root directory to use instead of your MEDIA_ROOT
  --remove-missing
                        Remove any existing keys from the bucket that are not
                        present in your local. DANGEROUS!
  --dry-run
                        Do a dry-run to show what files would be affected.

"""
import optparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

import boto

from s3sync.storage import cache
from s3sync.utils import (ConfigMissingError, get_aws_info, get_bucket_and_key,
    get_pending_key, get_pending_delete_key,
    upload_file_to_s3)


class Command(BaseCommand):
    # Extra variables to avoid passing these around
    upload_count = 0
    remaining_count = 0
    deleted_count = 0
    remaining_delete_count = 0

    option_list = BaseCommand.option_list + (
        optparse.make_option('-p', '--prefix',
            dest='prefix',
            default='',
            help="The prefix to prepend to the path on S3."),
        optparse.make_option('-d', '--dir',
            dest='dir',
            default='',
            help="The root directory to use instead of your MEDIA_ROOT"),
        optparse.make_option('--remove-missing',
            action='store_true', dest='remove_missing', default=False,
            help="Remove keys in the bucket for files locally missing."),
        optparse.make_option('--dry-run',
            action='store_true', dest='dry_run', default=False,
            help="Do a dry-run to show what files would be affected."),
    )

    help = 'Uploads the pending files from cache key.'

    def handle(self, *args, **options):
        # Check for AWS keys in settings
        try:
            get_aws_info()
        except ConfigMissingError:
            raise CommandError('Missing AWS keys from settings file. ' +
                ' Please supply both AWS_ACCESS_KEY_ID and ' +
                'AWS_SECRET_ACCESS_KEY.')

        self.DIRECTORY = options.get('dir')
        if not self.DIRECTORY:
            self.DIRECTORY = getattr(settings, 'MEDIA_ROOT', '')
        if not self.DIRECTORY:
            raise CommandError('Empty directory. Define MEDIA_ROOT or use '
                ' --dir=dirname')

        self.verbosity = int(options.get('verbosity'))
        self.prefix = options.get('prefix')
        self.remove_missing = options.get('remove_missing')
        self.dry_run = options.get('dry_run')

        if not hasattr(settings, 'BUCKET_UPLOADS'):
            raise CommandError('Please specify the name of your upload bucket.'
                ' Set BUCKET_UPLOADS in your settings.py')
        self.bucket, self.key = get_bucket_and_key(settings.BUCKET_UPLOADS)
        # Now call the syncing method to walk the MEDIA_ROOT directory and
        # upload all files found.
        self.upload_pending_to_s3()
        if self.remove_missing:
            self.delete_pending_from_s3()

        print
        print "%d files uploaded (%d remaining)." % (self.upload_count,
                                                        self.remaining_count)
        if self.remove_missing:
            print "%d files deleted (%s remaining)." % (self.deleted_count,
                                                self.remaining_delete_count)
        if self.dry_run:
            print 'THIS IS A DRY RUN, NO ACTUAL CHANGES.'

    def delete_pending_from_s3(self):
        """Gets the pending filenames from cache and deletes them."""
        pending_delete_key = get_pending_delete_key()
        pending = cache.get(pending_delete_key, [])
        remaining = []
        for i, file_key in enumerate(pending):
            prefixed_file_key = '%s/%s' % (self.prefix, file_key)
            if self.verbosity > 0:
                print "Deleting %s..." % prefixed_file_key
            if self.dry_run:
                self.deleted_count += 1
                continue
            failed = True
            try:
                self.bucket.delete_key(prefixed_file_key)
            except boto.exception.S3ResponseError, e:
                # TODO: retry to delete a few times
                print "Failed to delete: %s" % e
            except Exception, e:
                print e
                raise
            else:
                failed = False
                self.deleted_count += 1
            finally:
                if failed:
                    remaining.append(file_key)
                    self.remaining_delete_count += 1

        if not self.dry_run:
            cache.set(pending_delete_key, remaining)

    def upload_pending_to_s3(self):
        """Gets the pending filenames from cache and uploads them."""
        pending_key = get_pending_key()
        pending = cache.get(pending_key, [])
        remaining = []

        for i, file_key in enumerate(pending):
            prefixed_file_key = '%s/%s' % (self.prefix, file_key)
            if self.verbosity > 0:
                print "Uploading %s..." % prefixed_file_key
            if self.dry_run:
                self.upload_count += 1
                continue
            filename = self.DIRECTORY + '/' + file_key
            failed = True
            try:
                upload_file_to_s3(prefixed_file_key, filename, self.key,
                    do_gzip=True, do_expires=True)
            except boto.exception.S3CreateError, e:
                # TODO: retry to create a few times
                print "Failed to upload: %s" % e
            except Exception, e:
                print e
                raise
            else:
                failed = False
                self.upload_count += 1
                cache.delete(file_key)
            finally:
                if failed:
                    remaining.append(file_key)
                    self.remaining_count += 1

        if not self.dry_run:
            cache.set(pending_key, remaining)
