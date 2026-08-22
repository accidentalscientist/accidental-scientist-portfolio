from django.db import models
from django.utils.text import slugify
from django.utils import timezone
from django.db.models import Count
from markdownx.models import MarkdownxField
import re



class Project(models.Model):
    # Mirrors BlogPost.Category so projects and writing share one taxonomy.
    class Category(models.TextChoices):
        ENERGY = 'energy', 'Energy Systems'
        DATA = 'data', 'Data Stories'
        SPORT = 'sport', 'Human Performance'
        COMMERCIAL = 'commercial', 'Commercial Intelligence'

    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True, null=True)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.ENERGY)
    image = models.ImageField(upload_to='projects/', blank=True, null=True)
    project_url = models.URLField(blank=True, null=True)
    date = models.DateField(auto_now_add=True)
    # Used only for catalogue ranking; the public cards deliberately do not
    # expose maintenance metadata as editorial content.
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1

            while Project.objects.filter(slug=slug).exists():
                counter += 1
                slug = f"{base_slug}-{counter}"

            self.slug = slug
        super().save(*args, **kwargs)



class BlogPost(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'

    class Category(models.TextChoices):
        ENERGY = 'energy', 'Energy Systems'
        DATA = 'data', 'Data Stories'
        SPORT = 'sport', 'Human Performance'
        COMMERCIAL = 'commercial', 'Commercial Intelligence'

    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    summary = models.TextField(blank=True)
    key_takeaway = models.TextField(blank=True, help_text='Optional one-sentence insight shown prominently on the article page.')
    content = MarkdownxField()
    image = models.ImageField(upload_to='blog/', blank=True, null=True)
    published = models.DateField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PUBLISHED)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.ENERGY)
    is_featured = models.BooleanField(default=False)
    external_url = models.URLField(blank=True, null=True)

    class Meta:
        ordering = ['-published']

    def __str__(self):
        return self.title

    @property
    def reading_time_minutes(self):
        # Markdown table rows are excluded from the word count: a reader
        # examines a table's shape and headline numbers rather than reading
        # every cell as prose, so counting cell contents as words inflated
        # dense, table-heavy articles far beyond their actual reading time.
        prose = re.sub(r'(?m)^\s*\|.*\|\s*$', '', self.content)
        word_count = len(re.findall(r'\b\w+\b', prose))
        reading_seconds = (word_count / 200) * 60
        # A brief, fixed allowance per image: a reader looks at a chart
        # rather than reading it word by word, so this adds real but
        # bounded time instead of letting image-heavy articles read as
        # arbitrarily long. Counted from the placeholders already in the
        # content, so it needs no extra query for the image count.
        image_count = len(re.findall(r'\[\[image\d+\]\]', self.content)) + (1 if self.image else 0)
        reading_seconds += image_count * 12
        return max(1, round(reading_seconds / 60))

class BlogImage(models.Model):
    post = models.ForeignKey(BlogPost, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='blog/')
    caption = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Image for {self.post.title} ({self.order})"


class Contact(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    message = models.TextField()
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message from {self.name}"

