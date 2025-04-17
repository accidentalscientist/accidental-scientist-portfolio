# portfolio/management/commands/seed_data.py
from django.core.management.base import BaseCommand
from portfolio.models import Project, BlogPost
from django.utils.text import slugify
from django.utils.timezone import now

class Command(BaseCommand):
    help = 'Seed the database with sample blog posts and projects'

    def handle(self, *args, **kwargs):
        BlogPost.objects.all().delete()
        Project.objects.all().delete()

        self.stdout.write(self.style.WARNING('Old data cleared.'))

        for i in range(1, 7):
            project = Project.objects.create(
                title=f"Project {i} — Data Energy",
                description=f"Detailed description for Project {i}, highlighting sustainable data tooling.",
                image=None,
                project_url=f"https://github.com/accidentalscientist/project-{i}",
                date=now()
            )
            self.stdout.write(self.style.SUCCESS(f"Created: {project.title}"))

        for i in range(1, 7):
            post = BlogPost.objects.create(
                title=f"Blog Post {i} — Reflections",
                slug=slugify(f"blog-post-{i}"),
                summary=f"Quick thoughts on challenge {i} in the climate-tech space.",
                content=f"This is blog content body #{i}. Exploring project learning, green tech, and sustainability...",
                image=None,
                published=now()
            )
            self.stdout.write(self.style.SUCCESS(f"Created: {post.title}"))