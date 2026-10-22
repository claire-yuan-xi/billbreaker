# Bill Breaker

Plain-language explanations of US federal and state bills, with live AP
legislation headlines, saved bills, share links and an admin view of the
fine-tuned model.

## Stack

- Python: FastAPI server, Jinja HTML templates, SQLite (Turso when deployed)
  for the cache, share links and rate limits (`billbreaker/`)
- Notebooks: the model training notebook and a walkthrough of the site's
  pipeline (`notebooks/`)
- Browser: small JavaScript modules for animation (GSAP, Lenis) and the
  interactive bits (`billbreaker/static/js/`), styled with Tailwind

## Run it

```sh
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env        # add GEMINI_API_KEY, and OPENSTATES_API_KEY for state bills
uvicorn billbreaker.main:app --reload --port 3000
```

Open http://localhost:3000.

## Common tasks

| Task                   | Command                                   |
| ---------------------- | ----------------------------------------- |
| Run the tests          | `pytest`                                  |
| Rebuild the CSS        | `scripts/build-css.sh` (add `--watch`)    |
| Open the notebooks     | `jupyter lab notebooks`                   |
| Regenerate depth map   | `python3 scripts/make-depth-map.py ...`   |

`billbreaker/static/css/app.css` is committed, so the CSS only needs a rebuild
after changing classes in templates or JS.

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

Vercel (free) with a free Turso database; steps in [docs/deploy-vercel.md](docs/deploy-vercel.md).
