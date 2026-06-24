from django.contrib import admin
from markdownx.admin import MarkdownxModelAdmin
from .models import Project, BlogPost, BlogImage, Contact


class BlogImageInline(admin.TabularInline):
    model = BlogImage
    fields = ('image', 'caption', 'order')
    extra = 1


class BlogPostAdmin(MarkdownxModelAdmin):
    list_display = ('title', 'category', 'status', 'published', 'updated_at', 'is_featured')
    list_editable = ('category', 'status', 'is_featured')
    list_filter = ('status', 'category', 'is_featured', 'published')
    prepopulated_fields = {'slug': ('title',)}
    search_fields = ('title', 'summary', 'content')
    readonly_fields = ('updated_at',)
    inlines = [BlogImageInline]
    fieldsets = (
        ('Article', {
            'fields': ('title', 'slug', 'category', 'status', 'published', 'updated_at', 'is_featured'),
        }),
        ('Writing', {
            'fields': ('summary', 'key_takeaway', 'content'),
        }),
        ('Visuals & source', {
            'fields': ('image', 'external_url'),
        }),
    )


class ProjectAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("title",)}
    list_display = ('title', 'slug', 'date')
    fields = ('title', 'slug', 'description', 'image', 'project_url')
    readonly_fields = ('date',)


admin.site.register(Project, ProjectAdmin)
admin.site.register(BlogPost, BlogPostAdmin)
admin.site.register(BlogImage)
admin.site.register(Contact)
