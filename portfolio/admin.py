from django.contrib import admin
from .models import Project, BlogPost

class BlogPostAdmin(admin.ModelAdmin):
    list_display = ('title', 'published', 'is_featured')
    list_editable = ('published', 'is_featured')
    list_filter = ('is_featured', 'published')


admin.site.register(Project)
admin.site.register(BlogPost, BlogPostAdmin)
