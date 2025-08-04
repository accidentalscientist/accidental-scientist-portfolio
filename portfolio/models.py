from django.db import models
from django.utils.text import slugify
from django.utils import timezone
from django.db.models import Count



class Project(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True, null=True)
    description = models.TextField()
    image = models.ImageField(upload_to='projects/', blank=True, null=True)
    project_url = models.URLField(blank=True, null=True)
    date = models.DateField(auto_now_add=True)

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
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    summary = models.TextField(blank=True)
    content = models.TextField()
    image = models.ImageField(upload_to='blog/', blank=True, null=True)
    published = models.DateField(default=timezone.now)
    is_featured = models.BooleanField(default=False)
    external_url = models.URLField(blank=True, null=True)

    class Meta:
        ordering = ['-published']

    def __str__(self):
        return self.title

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

