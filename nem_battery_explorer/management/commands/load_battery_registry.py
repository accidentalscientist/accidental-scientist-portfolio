from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ...registry import DEFAULT_REGISTRY_PATH, RegistryError, load_registry


class Command(BaseCommand):
    help = 'Validate and upsert the versioned NEM battery registry.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=Path,
            default=DEFAULT_REGISTRY_PATH,
            help='Registry JSON file. Defaults to the project-owned v1 registry.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Validate and exercise database constraints, then roll back.',
        )

    def handle(self, *args, **options):
        try:
            result = load_registry(options['file'], dry_run=options['dry_run'])
        except RegistryError as exc:
            raise CommandError(str(exc)) from exc

        mode = 'Validated' if options['dry_run'] else 'Loaded'
        self.stdout.write(self.style.SUCCESS(
            f'{mode} battery registry: '
            f'{result.assets_created} assets created, {result.assets_updated} updated; '
            f'{result.registrations_created} registrations created, '
            f'{result.registrations_updated} updated.'
        ))
