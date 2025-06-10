import os
from django.core.management.base import BaseCommand
from portfolio.models import BlogPost
from django.utils.text import slugify
import nbformat
import markdown as md
import re
import random
from datetime import datetime
from nbconvert import HTMLExporter

NOTEBOOK_ROOT = r'C:\Data\projects\daily_data_analytics\daily_data_analytics_may2025'
GITHUB_ROOT = 'https://github.com/accidentalscientist/daily-data-analytics-may2025/blob/main/'

# funciton list

# summarise conclusion only
def extract_conclusion(nb):
    md_cells = [cell['source'] for cell in nb.cells if cell['cell_type'] == 'markdown']
    if not md_cells:
        return ""
    return md_cells[-1] 

# summarise intro, random middle, conclusion
def extract_intro_middle_conclusion(nb):
    md_cells = [cell['source'] for cell in nb.cells if cell['cell_type'] == 'markdown']
    if not md_cells:
        return ""
    intro = md_cells[0]
    conclusion = md_cells[-1]
    middle = ""
    if len(md_cells) > 2:
        middle = random.choice(md_cells[1:-1])
        content = "\n\n---\n\n".join([intro, middle, conclusion])
    elif len(md_cells) == 2:
        content = "\n\n---\n\n".join([intro, conclusion])
    else:
        content = intro
    return content

def strip_md_headers(md):
    return re.sub(r'(?m)^#+\s*', '', md)

# default is may 2025, for june 2025: publish_date = get_publish_date_from_rel_path(rel_path, month=6, year=2025)
def get_publish_date_from_rel_path(rel_path, month=5, year=2025):
    match = re.search(r'day(\d{1,2})', rel_path)
    if match:
        day = int(match.group(1))
        try:
            return datetime(year, month, day).date()
        except ValueError:
            return datetime(year, month, 1).date()
    return datetime.now().date()

# main command

class Command(BaseCommand):
    help = 'Import Jupyter notebooks as blog posts'

    def handle(self, *args, **kwargs):
        print("Import script started")
        print(f"NOTEBOOK_ROOT = {NOTEBOOK_ROOT}")
        for root, dirs, files in os.walk(NOTEBOOK_ROOT):
            dirs[:] = [d for d in dirs if not d.startswith('.') and not d.startswith('__')]
            for filename in files:
                if not filename.endswith('.ipynb'):
                    continue
                try:
                    print("Found notebook:", os.path.join(root, filename))
                    rel_path = os.path.relpath(os.path.join(root, filename), NOTEBOOK_ROOT)
                    filepath = os.path.join(root, filename)
                    nb = nbformat.read(filepath, as_version=4)
                    title = filename.replace('.ipynb', '').replace('_', ' ').title()
                    slug = slugify(title)
                    parts = rel_path.replace("\\", "/").split("/")
                    parts[-1] = parts[-1].replace("_", "-")
                    github_url = GITHUB_ROOT + rel_path.replace("\\", "/")
                    publish_date = get_publish_date_from_rel_path(rel_path)
                    summary = strip_md_headers(extract_conclusion(nb))
                    content = strip_md_headers(extract_intro_middle_conclusion(nb))
                    content_html = md.markdown(content)
                    post, created = BlogPost.objects.update_or_create(
                        slug=slug,
                        defaults={
                            'title': title,
                            'summary': summary,
                            'content': content,
                            'is_featured': False,
                            'external_url': github_url,
                            'published': publish_date,
                        }
                    )
                    self.stdout.write(self.style.SUCCESS(
                        f'{"Created" if created else "Updated"}: {title}'
                    ))
                except Exception as e:
                    print(f"Error processing {filename}: {e}")
