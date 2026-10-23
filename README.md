# Campus Bridge

Campus Bridge is a Flask and SQLite learning portal for students, faculty, and campus administrators. It combines course resources, assignments, attendance, coding practice, assessments, code rooms, and campus chat in one responsive interface.

Faculty can publish timetable sessions for assigned sections; students see only the sessions matching their semester and section. The coding leaderboard uses points earned through coding challenges and assessments.

## Run locally

1. Use Python 3.9 or newer. Create a virtual environment and install dependencies:

   ```powershell
   py -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and set a unique `SECRET_KEY`. Third-party API keys can stay blank to disable those integrations.
3. Start the server with `py app.py` and open `http://127.0.0.1:5000/`.

By default, the app creates a local database at `DATABASE_PATH` or `campus_bridge.db` and fills its eight semester catalogs with starter course content. New databases still have no user accounts; administrators create faculty and student accounts in the application. The catalog is sample curriculum content, not an official university syllabus. To use Supabase, set both `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`, then apply [`supabase_schema.sql`](supabase_schema.sql) in the Supabase SQL editor. That script creates the catalog tables if needed and inserts missing starter courses; it is safe to reapply. Applying it is required for the content to be present in a deployed Supabase database. The service-role key must stay on the server and must never be added to browser code. For a disposable local demo database, set `SEED_DEMO_DATA=true` and `DEMO_PASSWORD` (at least 12 characters) before first launch. Seeded demo accounts share that password. Do not use demo seeding in production.

## Optional integrations

- `JUDGE0_API_KEY` enables code execution and coding-assessment grading.
- `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` select the Supabase database instead of local SQLite.
- `COHERE_API_KEY` enables the in-app AI assistant, career recommendations, and code-review endpoint.
- `COHERE_MODEL` selects the Cohere Chat model; it defaults to `command-a-plus-05-2026`.
- `GEMINI_API_KEY` configures the standalone `CodeReviewBot` helper.
- `COOKIE_SECURE=true` enables secure session cookies when serving over HTTPS.

## Architecture

- `app.py` contains Flask routes, role checks, and integration workflows.
- `db.py` selects Supabase when configured, otherwise initializes SQLite; a compatibility adapter keeps the existing route queries consistent.
- `templates/` contains Jinja screens, shared layouts, and role navigation.
- `static/css/` and `static/js/` contain the light design system and browser behavior.
- `campus_bridge.db` is runtime state and is excluded from version control.

## Security and deployment

Passwords use bcrypt. Protected routes verify the role from SQLite, and account creation is restricted to administrators. Store secrets in the deployment environment, use HTTPS, set a stable random `SECRET_KEY`, and back up the SQLite database. Third-party execution and AI features require API credentials.

For deployment, run behind a production WSGI server such as Gunicorn. SQLite requires persistent storage and a single application instance; Supabase supports a shared database across application instances. On Vercel, SQLite defaults to `/tmp/campus_bridge.db` so the app can run for disposable demos, but that filesystem is temporary and is not shared across function instances. Use Supabase for persistent Vercel data.

## License

See [LICENSE](LICENSE).
