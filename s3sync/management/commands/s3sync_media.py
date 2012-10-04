"""
Sync Media to S3
================

Django command that scans all files in your settings.MEDIA_ROOT folder and
uploads them to S3 with the same directory structure.

This command can optionally do the following but it is off by default:
* gzip compress any CSS and Javascript files it finds and adds the appropriate
  'Content-Encoding' header.
* set a far future 'Expires' header for optimal caching.

Note: This script requires the Python boto library and valid Amazon Web
Services API keys.

Required settings.py variables:
AWS_ACCESS_KEY_ID = ''
AWS_SECRET_ACCESS_KEY = ''

Command options are:
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

"""
import datetime
from fnmatch import fnmatch
try:
    from hashlib import md5
except ImportError:
    from md5 import md5
import optparse
import os
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from s3sync.utils import (get_aws_info, get_bucket_and_key, ConfigMissingError,
    upload_file_to_s3)

# Make sure boto is available
try:
    import boto
    import boto.exception
    from boto.s3.bucketlistresultset import bucket_lister
except ImportError:
    raise ImportError("The boto Python library is not installed.")


class Command(BaseCommand):
    # Extra variables to avoid passing these around
    AWS_ACCESS_KEY_ID = ''
    AWS_SECRET_ACCESS_KEY = ''
    AWS_BUCKET_NAME = ''
    DIRECTORY = ''
    EXCLUDE_LIST = []

    upload_count = 0
    skip_count = 0
    remove_bucket_count = 0

    option_list = BaseCommand.option_list + (
        optparse.make_option('-b', '--bucket',
            dest='bucket', default='',
            help="The name of the Amazon bucket you are uploading to."),
        optparse.make_option('-p', '--prefix',
            dest='prefix',
            default='',
            help="The prefix to prepend to the path on S3."),
        optparse.make_option('-d', '--dir',
            dest='dir', default=settings.MEDIA_ROOT,
            help="The root directory to use instead of your MEDIA_ROOT"),
        optparse.make_option('--gzip',
            action='store_true', dest='gzip', default=False,
            help="Enables gzipping CSS and Javascript files."),
        optparse.make_option('--expires',
            action='store_true', dest='expires', default=False,
            help="Enables setting a far future expires header."),
        optparse.make_option('--force',
            action='store_true', dest='force', default=False,
            help="Skip the file mtime check to force upload of all files."),
        optparse.make_option('--remove-missing',
            action='store_true', dest='remove_missing', default=False,
            help="Remove keys in the bucket for files locally missing."),
        optparse.make_option('--dry-run',
            action='store_true', dest='dry_run', default=False,
            help="Do a dry-run to show what files would be affected."),
        optparse.make_option('--exclude-list', dest='exclude_list',
            action='store', default='',
            help="Override default directory and file exclusion filters. "
                 "(enter as comma separated line)"),
        # TODO: implement
        optparse.make_option('--hash-chunk-size', dest='hash_chunk',
            action='store', default=4096,
            help="Override default directory and file exclusion filters. "
                 "(enter as comma separated line)"),
    )

    help = ('Syncs the complete MEDIA_ROOT structure and files to S3 into '
            'the given bucket name.')

    def handle(self, *args, **options):
        # Check for AWS keys in settings
        try:
            self.AWS_ACCESS_KEY_ID, self.AWS_SECRET_ACCESS_KEY, self.AWS_S3_HOST = get_aws_info()
        except ConfigMissingError:
            raise CommandError('Missing AWS keys from settings file. ' +
                ' Please supply both AWS_ACCESS_KEY_ID and ' +
                'AWS_SECRET_ACCESS_KEY.')

        self.AWS_ACCESS_KEY_ID = settings.AWS_ACCESS_KEY_ID
        self.AWS_SECRET_ACCESS_KEY = settings.AWS_SECRET_ACCESS_KEY
        self.AWS_BUCKET_NAME = options.get('bucket')

        if not self.AWS_BUCKET_NAME:
            raise CommandError('No bucket specified. Use --bucket=name')

        if not settings.MEDIA_ROOT:
            raise CommandError('MEDIA_ROOT must be set in your settings.')

        self.verbosity = int(options.get('verbosity'))
        # TODO: compare first hash chunk of files to see if they're identical
        self.hash_chunk = int(options.get('hash_chunk'))
        self.prefix = options.get('prefix')
        self.do_gzip = options.get('gzip')
        self.do_expires = options.get('expires')
        self.do_force = options.get('force')
        self.remove_missing = options.get('remove_missing')
        self.dry_run = options.get('dry_run')
        self.DIRECTORY = options.get('dir')
        exclude_list = options.get('exclude_list')
        if exclude_list and isinstance(exclude_list, list):
            # command line option overrides default exclude_list
            self.EXCLUDE_LIST = exclude_list
        elif exclude_list:
            self.EXCLUDE_LIST = exclude_list.split(',')

        # Now call the syncing method to walk the MEDIA_ROOT directory and
        # upload all files found.
        self.sync_s3()

        print
        print "%d files uploaded." % (self.upload_count)
        print "%d files skipped." % (self.skip_count)
        if self.remove_missing:
            print "%d keys removed from bucket." % (self.remove_bucket_count)
        if self.dry_run:
            print 'THIS IS A DRY RUN, NO ACTUAL CHANGES.'

    def sync_s3(self):
        """
        Walks the media directory and syncs files to S3
        """
        bucket, key = get_bucket_and_key(self.AWS_BUCKET_NAME)
        self.s3_files = {}
        self.files_processed = set()
        os.path.walk(self.DIRECTORY, self.upload_s3,
            (bucket, key, self.AWS_BUCKET_NAME, self.DIRECTORY))

        # Remove files on bucket if they're missing locally
        if self.remove_missing:
            self.remove_s3(bucket)

    def find_key_in_list(self, s3_list, file_key):
        if file_key in self.s3_files:
            return self.s3_files[file_key]
        for s3_key in s3_list:
            if s3_key.name == file_key:
                return s3_key
            if s3_key.name not in self.files_processed:
                self.s3_files[s3_key.name] = s3_key
        return None

    def finish_list(self, s3_list):
        for s3_key in s3_list:
            if s3_key.name not in self.files_processed:
                self.s3_files[s3_key.name] = s3_key

    def remove_s3(self, bucket):
        print
        if not self.s3_files:
            if self.verbosity > 0:
                print 'No files to remove.'
            return

        for key, value in self.s3_files.items():
            if not self.dry_run:
                bucket.delete_key(value.name)
            self.remove_bucket_count += 1
            print "Deleting %s..." % (key)

    def upload_s3(self, arg, dirname, names):
        """
        This is the callback to os.path.walk and where much of the work happens
        """
        bucket, key, bucket_name, root_dir = arg

        # Skip files and directories we don't want to sync
        for pattern in self.EXCLUDE_LIST:
            if fnmatch(os.path.basename(dirname), pattern):
                if self.verbosity > 1:
                    print 'Skipping: %s (rule: %s)' % (names, pattern)
                del names[:]
                return

        # Later we assume the MEDIA_ROOT ends with a trailing slash
        if not root_dir.endswith(os.path.sep):
            root_dir = root_dir + os.path.sep

        list_prefix = dirname[len(root_dir):]
        if self.prefix:
            list_prefix = '%s/%s' % (self.prefix, list_prefix)
        s3_list = bucket_lister(bucket, prefix=list_prefix)

        for name in names:
            bad_name = False
            for pattern in self.EXCLUDE_LIST:
                if fnmatch(name, pattern):
                    bad_name = True  # Skip files we don't want to sync
            if bad_name:
                if self.verbosity > 1:
                    print 'Skipping: %s (rule: %s)' % (names, pattern)
                continue

            filename = os.path.join(dirname, name)
            if os.path.isdir(filename):
                continue  # Don't try to upload directories

            file_key = filename[len(root_dir):]
            if self.prefix:
                file_key = '%s/%s' % (self.prefix, file_key)

            # Check if file on S3 is older than local file, if so, upload
            # TODO: check if hash chunk corresponds
            if not self.do_force:
                s3_key = self.find_key_in_list(s3_list, file_key)
                if s3_key:
                    s3_datetime = datetime.datetime(*time.strptime(
                        s3_key.last_modified, '%Y-%m-%dT%H:%M:%S.000Z')[0:6])
                    local_datetime = datetime.datetime.utcfromtimestamp(
                        os.stat(filename).st_mtime)
                    if local_datetime < s3_datetime:
                        self.skip_count += 1
                        if self.verbosity > 1:
                            print "File %s hasn't been modified since last " \
                                "being uploaded" % (file_key)
                        if file_key in self.s3_files:
                            self.files_processed.add(file_key)
                            del self.s3_files[file_key]
                        continue
            if file_key in self.s3_files:
                self.files_processed.add(file_key)
                del self.s3_files[file_key]

            # File is newer, let's process and upload
            if self.verbosity > 0:
                print "Uploading %s..." % file_key
                if self.dry_run:
                    self.upload_count += 1
                    continue

            try:
                upload_file_to_s3(file_key, filename, key,
                    do_gzip=self.do_gzip, do_expires=self.do_expires,
                    verbosity=self.verbosity)
            except boto.exception.S3CreateError, e:
                # TODO: retry to create a few times
                print "Failed to upload: %s" % e
            except Exception, e:
                print e
                raise
            else:
                self.upload_count += 1

        # If we don't care about what's missing, wipe this to save memory.
        if not self.remove_missing:
            self.s3_files = {}
        else:
            self.finish_list(s3_list)
