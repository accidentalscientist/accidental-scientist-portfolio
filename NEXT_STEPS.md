# Next steps — after the v2.7.0 deployment

A checklist of the things only you can do (and a few recommended follow-ups).
Work top to bottom; the first three are the important ones.

---

## 1. Set the production environment variables (server `.env`)

Add this **required** line so static files collect to the right place:

```
STATIC_ROOT=/var/www/accidental-site/staticfiles
```

Then redeploy (collectstatic + restart). After confirming the site loads over
HTTPS, add these to switch on the last two security headers:

```
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
```

Restart Gunicorn. Then run, on the server, with the production config:

```
sudo -u thibault bash -c 'cd /home/thibault/accidental-scientist-portfolio && venv/bin/python manage.py check --deploy'
```

It should report no serious warnings. Confirm `DEBUG=False`.

---

## 2. Get the site discoverable (your priority)

These off-site actions are what actually move the needle — the on-page SEO is
already built (sitemap, structured data, titles, OG).

1. **Google Search Console** — go to search.google.com/search-console, add
   `accidentalscientist.net`, verify (DNS TXT or the HTML-tag method), then
   **submit `https://accidentalscientist.net/sitemap.xml`**. This gets you
   indexed and shows any crawl problems.
2. **Bing Webmaster Tools** (optional) — same sitemap; quick to add.
3. **Backlinks with the anchor text "Accidental Scientist"** — this is the
   single biggest lever for ranking on the brand term:
   - LinkedIn → add the site as a **Featured** link and mention "Accidental
     Scientist" in your About.
   - **GitHub profile README** → link to the site by name.
   - Email signature, and any communities/directories you're part of.
4. **After ~1 week** — check Search Console "Pages" to confirm indexing, and
   Google `site:accidentalscientist.net` to see what's indexed.

> Realistic outcome: your name and domain rank quickly once indexed; the bare
> term "accidental scientist" is a medium-term game won by the backlinks above
> plus steady publishing. Do **not** keyword-stuff articles — it backfires.

---

## 3. Upload the content that isn't in git

- **Guided meditation MP3** — admin → Stillpoint → Guided meditations → Add.
  The old WAV was removed; only **MP3** is accepted now.
- **NEM CSV** — admin → Nem_dashboard → Fuel data uploads → Add (if the live
  dashboard needs data). The import summary now shows on the upload row.

---

## 4. Server hardening (invisible, no control change)

```
sudo apt update && sudo apt -y upgrade        # patch the OS
sudo apt install -y fail2ban                   # auto-blocks brute-force attempts
sudo systemctl enable --now fail2ban
```

fail2ban won't affect your own logins. (We deliberately did **not** force
SSH keys-only or admin 2FA, to avoid any lock-out — revisit when you're ready.)

---

## 5. Verify

- Submit a test message through the **contact form** and confirm it arrives.
- Check **/about/** loads and **/contact/** redirects to it.
- Check **/projects/** shows the category pills (NEM = Energy transition,
  Stillpoint = Human performance).

---

## 6. Recommended follow-ups (separate, low-risk changes)

Deliberately **not** bundled into this stability release:

- **CSS split** — break `style.css` into per-area partials for readability
  (optionally with django-compressor for minification). Isolated change, do it
  once this release is confirmed stable.
- **Dependency cleanup** — the requirements still carry an unused Wagtail stack
  (`django-modelcluster`, `treebeard`, `draftjs_exporter`, `telepath`, `laces`,
  `Willow`, …) and a Jupyter stack (left over from the now-deleted
  `import_notebooks` command). Remove carefully, testing after each batch, and
  run `pip-audit`.
- **Domain portability** — the NEM project URL is stored absolute; make it
  relative (`/nem/`) if you ever change domain.
- **2FA / SSH keys-only** — when you're comfortable you won't lock yourself out.

---

## Content-trust policy (documented, per the security review)

All site content — article Markdown, image captions, article metadata, and the
imported article packages — is **authored and controlled solely by the site
owner**. The rendering pipeline therefore treats this content as trusted; full
HTML sanitisation was intentionally not added (captions are escaped as basic
hygiene). If guest authorship is ever introduced, revisit this with a
sanitising renderer (e.g. `bleach`).
