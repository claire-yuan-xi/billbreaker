# Deploy on Vercel

The site runs on Vercel's free Hobby plan as one Python function, and the
storage lives in a free Turso database. Neither needs a card. The site never
sleeps, and share links and cached breakdowns are kept.

## First deploy

1. Sign in at vercel.com with GitHub and choose the free Hobby plan.
2. Click Add New, then Project, then import `bill-breaker`. Leave every
   setting as it is and click Deploy. `pyproject.toml` tells Vercel where the
   app is.
3. In the project, open Storage, click Create, pick Turso, choose the free
   plan, and connect it to the project. This adds `TURSO_DATABASE_URL` and
   `TURSO_AUTH_TOKEN` for you.
4. Open Settings, then Environment Variables, and add `GEMINI_API_KEY`.
5. Open Deployments and click Redeploy on the latest one so it picks up the
   new settings. Then open the `vercel.app` link.

The tables are created on the first request, so there is nothing to set up
in Turso.

## Move billbreaker.org

Do this only once the vercel.app link works.

1. In Vercel, open Settings, then Domains, and add `billbreaker.org` and
   `www.billbreaker.org`.
2. In Cloudflare, open Workers and Pages, then the billbreaker worker, then
   Settings, then Domains and Routes, and remove both custom domains.
3. In Cloudflare DNS for billbreaker.org, add the records Vercel shows,
   usually:
   - `A` `@` to `76.76.21.21`, proxy off (grey cloud)
   - `CNAME` `www` to `cname.vercel-dns.com`, proxy off
4. Vercel checks the records and turns on HTTPS by itself.

To go back, delete those two records and re-add the worker's custom domains.

## Later

- Model: nothing to set. /admin/ml runs it in the browser from the Hugging Face repo clairexi/bill-breaker-t5-onnx.
- Every push to main redeploys.
