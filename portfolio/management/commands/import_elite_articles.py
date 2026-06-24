import json
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from portfolio.models import BlogImage, BlogPost


class Command(BaseCommand):
    help = 'Import structured Elite Analytics article packages into BlogPost records.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source-dir',
            default=Path(settings.ELITE_ARTICLES_DIR) / 'articles',
            help='Directory containing one folder per article package.',
        )
        parser.add_argument(
            '--slug',
            help='Import only one article package by slug.',
        )
        parser.add_argument(
            '--publish',
            action='store_true',
            help='Publish imported articles. Omit to import them as drafts.',
        )

    def handle(self, *args, **options):
        source_dir = Path(options['source_dir'])
        if not source_dir.is_dir():
            raise CommandError(f'Article directory does not exist: {source_dir}')

        packages = sorted(path for path in source_dir.iterdir() if path.is_dir())
        if options['slug']:
            packages = [
                path
                for path in packages
                if (path / 'metadata.json').is_file()
                and json.loads((path / 'metadata.json').read_text(encoding='utf-8')).get('slug')
                == options['slug']
            ]
        if not packages:
            raise CommandError('No matching article packages were found.')

        status = BlogPost.Status.PUBLISHED if options['publish'] else BlogPost.Status.DRAFT
        imported = 0

        for package in packages:
            metadata_path = package / 'metadata.json'
            article_path = package / 'article.md'
            if not metadata_path.is_file() or not article_path.is_file():
                raise CommandError(f'{package.name} needs metadata.json and article.md')

            metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
            required = {'title', 'slug', 'category', 'summary', 'key_takeaway'}
            missing = required - metadata.keys()
            if missing:
                raise CommandError(f'{package.name} is missing: {", ".join(sorted(missing))}')

            sources = metadata.get('source_notebooks', [])
            post, created = BlogPost.objects.update_or_create(
                slug=metadata['slug'],
                defaults={
                    'title': metadata['title'],
                    'summary': metadata['summary'],
                    'key_takeaway': metadata['key_takeaway'],
                    'content': article_path.read_text(encoding='utf-8'),
                    'category': metadata['category'],
                    'status': status,
                    'is_featured': bool(metadata.get('featured', False)),
                    'external_url': sources[0] if sources else None,
                },
            )

            cover_image = metadata.get('cover_image')
            if cover_image:
                cover_path = package / cover_image
                if not cover_path.is_file():
                    raise CommandError(f'Cover image does not exist: {cover_path}')
                if not post.image or not post.image.name.endswith(cover_path.name):
                    with cover_path.open('rb') as image_file:
                        post.image.save(cover_path.name, File(image_file), save=True)

            for order, figure in enumerate(metadata.get('inline_figures', [])):
                figure_path = package / figure['file']
                if not figure_path.is_file():
                    raise CommandError(f'Inline figure does not exist: {figure_path}')
                image, _ = BlogImage.objects.get_or_create(post=post, order=order)
                image.caption = figure.get('caption', '')
                if not image.image or not image.image.name.endswith(figure_path.name):
                    with figure_path.open('rb') as image_file:
                        image.image.save(figure_path.name, File(image_file), save=False)
                image.save()

            imported += 1
            self.stdout.write(self.style.SUCCESS(
                f'{"Created" if created else "Updated"}: {post.title}'
            ))

        self.stdout.write(self.style.SUCCESS(f'Imported {imported} article package(s) as {status}.'))
