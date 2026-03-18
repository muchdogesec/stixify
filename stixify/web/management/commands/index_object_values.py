"""
Management command to index existing STIX objects from ArangoDB into ObjectValue table.

This command retrieves all objects for each file and processes them through the 
process_uploaded_objects_hook to populate the ObjectValue table.

Usage:
    python manage.py index_object_values
    python manage.py index_object_values --files <uuid> <uuid>
    python manage.py index_object_values --dry-run
"""

import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from arango import ArangoClient

from stixify.web.models import File
from stixify.web.values.values import process_uploaded_objects_hook


logger = logging.getLogger(__name__)


def validate_file_id(value):
    File.objects.get(pk=value)  # Will raise DoesNotExist if invalid
    return value


class Command(BaseCommand):
    help = "Index existing STIX objects from ArangoDB into ObjectValue table"

    def add_arguments(self, parser):
        parser.add_argument(
            "--files",
            type=validate_file_id,
            nargs="+",
            help="Process only specific files by UUID",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be processed without actually indexing",
        )

    def handle(self, *args, **options):
        file_ids = options.get("files")
        dry_run = options.get("dry_run")

        # Get files to process
        files = File.objects.all()
        if file_ids:
            files = files.filter(pk__in=file_ids)

        total_files = files.count()
        self.stdout.write(self.style.SUCCESS(f"Processing {total_files} file(s)"))

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )

        # Connect to ArangoDB
        client = ArangoClient(hosts=settings.ARANGODB_HOST_URL)
        db_name = settings.ARANGODB_DATABASE + "_database"
        db = client.db(
            db_name,
            username=settings.ARANGODB_USERNAME,
            password=settings.ARANGODB_PASSWORD,
            verify=True,
        )
        self.stdout.write(self.style.SUCCESS(f"Connected to ArangoDB: {db.db_name}"))

        total_objects = 0
        failed_files = []

        # Process each file individually
        for idx, file in enumerate(files, 1):
            collection_name = "stixify_vertex_collection"
            
            self.stdout.write(
                f"\n[{idx}/{total_files}] Processing file: {file.id}"
            )
            self.stdout.write(f"  Collection: {collection_name}")

            try:
                # Check if collection exists
                if not db.has_collection(collection_name):
                    self.stdout.write(
                        self.style.WARNING(
                            f"  Collection {collection_name} does not exist, skipping"
                        )
                    )
                    failed_files.append(
                        {
                            "file_id": str(file.id),
                            "error": f"Collection {collection_name} does not exist",
                        }
                    )
                    continue

                # Clear existing ObjectValues for this file
                if not dry_run:
                    deleted_count = file.object_values.all().delete()[0]
                    if deleted_count > 0:
                        self.stdout.write(f"  Cleared {deleted_count} existing ObjectValues")

                # Query objects for this specific file
                file_report_id = f"report--{file.id}"
                file_query = """
                    FOR doc IN @@collection
                        FILTER doc._stixify_report_id == @report_id
                        RETURN doc
                """

                cursor = db.aql.execute(
                    file_query,
                    bind_vars={
                        "report_id": file_report_id,
                        "@collection": collection_name,
                    },
                )
                file_objects = list(cursor)

                if not file_objects:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  No objects found for file {file.id}"
                        )
                    )
                    continue

                self.stdout.write(f"  Found {len(file_objects)} objects")

                if not dry_run:
                    try:
                        # Create a mock instance for the hook
                        mock_instance = type("MockInstance", (), {})()

                        # Call the hook
                        process_uploaded_objects_hook(
                            instance=mock_instance,
                            collection_name=collection_name,
                            objects=file_objects,
                        )

                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  Successfully indexed {len(file_objects)} objects"
                            )
                        )

                        total_objects += len(file_objects)
                    except Exception as e:
                        self.stderr.write(
                            self.style.ERROR(
                                f"  Error processing file {file.id}: {str(e)}"
                            )
                        )
                        logger.exception(
                            f"Error processing file {file.id}"
                        )
                        failed_files.append(
                            {
                                "file_id": str(file.id),
                                "error": str(e),
                            }
                        )
                else:
                    total_objects += len(file_objects)

            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(f"  Error processing file {file.id}: {str(e)}")
                )
                logger.exception(f"Error processing file {file.id}")
                failed_files.append(
                    {
                        "file_id": str(file.id),
                        "error": str(e),
                    }
                )
                continue

        # Summary
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS("SUMMARY"))
        self.stdout.write(f"Total files processed: {total_files}")
        self.stdout.write(f"Total objects indexed: {total_objects}")
        self.stdout.write(f"Failed files: {len(failed_files)}")

        if failed_files:
            self.stdout.write("\n" + self.style.ERROR("FAILED FILES:"))
            for failed in failed_files:
                self.stdout.write(
                    f"  - File: {failed['file_id']}, Error: {failed['error']}"
                )

        self.stdout.write("=" * 50)

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "\nDRY RUN COMPLETE - No changes were made to the database"
                )
            )
