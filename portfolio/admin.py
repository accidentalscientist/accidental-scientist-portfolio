from django.contrib import admin
from .models import Project, BlogPost, BlogImage, Contact


class BlogImageInline(admin.TabularInline):
    model = BlogImage
    fields = ('image', 'caption', 'order')
    extra = 1

class BlogPostAdmin(admin.ModelAdmin):
    list_display = ('title', 'published', 'is_featured')
    list_editable = ('published', 'is_featured')
    list_filter = ('is_featured', 'published')
    prepopulated_fields = {'slug': ('title',)}
    search_fields = ('title', 'summary')
    inlines = [BlogImageInline]


admin.site.register(Project)
admin.site.register(BlogPost, BlogPostAdmin)
admin.site.register(BlogImage)
admin.site.register(Contact)