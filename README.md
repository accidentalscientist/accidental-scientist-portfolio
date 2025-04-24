# 🧪 Accidental Scientist Portfolio

A full-stack Django portfolio + blog site for showcasing projects and writing posts, deployed via Nginx/Gunicorn on Ubuntu (DigitalOcean). Domain: [`accidentalscientist.net`](http://accidentalscientist.net)

---

## 🚀 Features

- 📝 Blog and Project sections (custom models)
- 🎨 Responsive frontend with dark/light toggle
- 🧠 Admin backend to manage content
- 📂 Markdown or rich text support (in progress)
- 🌐 Deployed to live domain with Nginx/Gunicorn
- 🔐 SSL/HTTPS setup (WIP)

---

## ⚙️ Setup Instructions

```bash
# Clone and enter
git clone https://github.com/your-user/accidental-site.git
cd accidental-site

# Set up env + install
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set up secret keys
cp .env.example .env  # and fill in SECRET_KEY etc.

# Migrate and run
python manage.py migrate
python manage.py runserver
