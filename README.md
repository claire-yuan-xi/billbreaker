# Bill Breaker

BillBreaker is a web app that translates dense legislative text into plain English for teens and young voters, with a personalized breakdown of how each bill would affect them.

## Stack

- Python: FastAPI server, Jinja HTML templates, SQLite (Turso when deployed)
  for the cache, share links and rate limits (`billbreaker/`)
- Notebooks: the model training notebook and a walkthrough of the site's
  pipeline (`notebooks/`)
- Browser: small JavaScript modules for animation (GSAP, Lenis) and the
  interactive bits (`billbreaker/static/js/`), styled with Tailwind

## Use it

billbreaker.org

## Layout

```
billbreaker/
  main.py           app setup, error pages
  pages.py          HTML routes
  api/              JSON and streaming endpoints
  services/         bill text, news, AI calls, cache, rate limits
  ml/               section ranking and claims check from the notebook
  templates/        Jinja pages and partials
  static/           CSS, JS modules, images, vendored GSAP and Lenis
notebooks/          model training and the site pipeline
tests/              pytest suite
docs/               deploying to Vercel, abuse monitoring
```

## Pages

- `/` home with headlines, saved bills and search
- `/bill?state=US&number=HR1` the AI breakdown of one bill
- `/b/<slug>` a published share link
- `/admin/ml` how the model ranks and explains a bill
- `/admin/abuse` rate-limit events (needs `ABUSE_ADMIN_TOKEN`)

## Hosting

Vercel in the free plan; bought a domain

## Pictures and Documentation

I utilized an API key that integrates my favorite not-for-profit news agency: AP news! This gives users ideas of what bills are on the floor based on news in the past 24 hours.
<img width="1470" height="800" alt="Screenshot 2026-11-03 at 10 09 21 AM" src="https://github.com/user-attachments/assets/9556dcba-69d8-4deb-8f3f-0bf45e48e323" />

I also made sure users can save past bills that they've searched.
<img width="1470" height="800" alt="Screenshot 2026-11-03 at 10 10 44 AM" src="https://github.com/user-attachments/assets/38bca1e3-73ae-4d1d-94c3-c29707674af8" />

One of the core features of the web app is the personalization, in which users can voluntarily answer questions about themselves to have the AI tailor its responses to the user!
<img width="706" height="762" alt="Screenshot 2026-11-03 at 10 11 16 AM" src="https://github.com/user-attachments/assets/99eb9960-dacc-46db-870a-0ec971c3a575" />

To keep API rate limits free, I made sure bill analyses would come from a cached analysis database. 
<img width="1470" height="802" alt="Screenshot 2026-11-03 at 10 12 13 AM" src="https://github.com/user-attachments/assets/a968b5c7-df1b-40c6-a14f-ef891a80b733" />






