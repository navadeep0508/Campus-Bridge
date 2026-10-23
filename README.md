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

By default, the app creates `campus_bridge.db` in the project folder (or uses `DATABASE_PATH` if set) and fills the eight semester catalogs with sample courses. A new database has no accounts; an administrator must create them, unless demo seeding is enabled below. The catalog is sample content, not an official university syllabus.

### Local demo accounts

To create sample accounts in a new local database, set `SEED_DEMO_DATA=true` and `DEMO_PASSWORD` in `.env` before starting the app. The password must be at least 12 characters. The app creates one admin, one faculty member, and two students; all four accounts use the value of `DEMO_PASSWORD`:

| Role | Demo email |
| --- | --- |
| Admin | `admin@gmail.com` |
| Faculty | `faculty@gmail.com` |
| Student | `23102a040719@mbu.asia` |
| Student | `raghs@gmail.com` |

Seeding runs only when the database has no users. It does not reset existing accounts or passwords. Use demo seeding only with disposable data.

### Vercel demo login

The deployed Vercel demo is configured to seed the same four accounts. Open the app’s **Sign in** page to see the email addresses and password:

**Shared password:** `CampusBridgeStudent2026!`

The admin account is public and can change or delete demo data. These credentials are for testing only. Do not enter real or private campus information.

Vercel uses SQLite at `/tmp/campus_bridge.db` for this demo. `/tmp` is temporary and may not be shared between function instances, so accounts or changes can disappear or differ between requests. This setup is not suitable for persistent or production data.

### Supabase setup

To use Supabase instead of SQLite, set `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`, then run [`supabase_schema.sql`](supabase_schema.sql) in the Supabase SQL editor. It creates the catalog tables and inserts missing sample courses, and is safe to reapply. The service-role key must remain server-side and must never be added to browser code.

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

For deployment, run behind a production WSGI server such as Gunicorn. SQLite requires persistent storage and a single application instance. The Vercel `/tmp` SQLite setup is demo-only; use Supabase or another persistent database for production data. Never use the public demo credentials in a real deployment.

## License

See [LICENSE](LICENSE).
