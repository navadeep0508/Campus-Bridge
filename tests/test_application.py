import bcrypt
import pytest
from types import SimpleNamespace

import app as application
import db as database


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "campus-test.sqlite3")
    database.init_db()
    application.app.config.update(TESTING=True, SECRET_KEY="test-secret")
    return application.app.test_client()


def add_user(email, role, **fields):
    password = bcrypt.hashpw(b"test-password-long", bcrypt.gensalt()).decode()
    return application.supabase.table("users").insert({
        "email": email,
        "password": password,
        "name": fields.pop("name", role.title()),
        "role": role,
        **fields,
    }).execute().data[0]


def login_session(client, user):
    with client.session_transaction() as session:
        session["user_id"] = user["id"]
        session["role"] = "admin"  # Middleware must replace this with the stored role.


def test_course_catalog_is_available_and_repeatable(client):
    with database._get_connection() as conn:
        for semester in range(1, 9):
            rows = conn.execute(f"SELECT course_code FROM semester{semester}").fetchall()
            assert len(rows) >= 3
            assert all(row["course_code"] for row in rows)

    # Startup can happen more than once; catalog content must not duplicate.
    database.init_db()
    with database._get_connection() as conn:
        rows = conn.execute("SELECT course_code FROM semester1 WHERE course_code = 'CSE101'").fetchall()
        assert len(rows) == 1

    student = add_user("catalog-student@example.test", "student", semester="1")
    login_session(client, student)
    response = client.get("/mycourse")
    assert response.status_code == 200
    assert b"Programming Fundamentals" in response.data


def test_role_is_verified_against_database(client):
    student = add_user("student@example.test", "student", semester="1")
    login_session(client, student)

    assert client.get("/compiler").status_code == 200
    assert client.get("/dashboard/admin").status_code == 302
    with client.session_transaction() as session:
        assert session["role"] == "student"


def test_attendance_edits_are_idempotent_per_class_date(client):
    faculty = add_user("faculty@example.test", "faculty")
    student = add_user("learner@example.test", "student", section="A")
    application.supabase.table("faculty_sections").insert({"faculty_id": faculty["id"], "section": "A"}).execute()
    application.supabase.table("attendance").insert({"student_id": student["id"], "section": "A", "attended_classes": 8, "total_classes": 10}).execute()
    login_session(client, faculty)
    payload = {"section": "A", "date": "2026-10-23", "attendance": [{"student_id": student["id"], "status": "present"}]}

    assert client.post("/mark_attendance", json=payload).status_code == 200
    payload["attendance"][0]["status"] = "absent"
    assert client.post("/mark_attendance", json=payload).status_code == 200
    record = application.supabase.table("attendance").select("attended_classes", "total_classes").eq("student_id", student["id"]).eq("section", "A").execute().data[0]
    assert record == {"attended_classes": 8, "total_classes": 11}


def test_faculty_timetable_is_scoped_and_prevents_overlaps(client):
    faculty = add_user("schedule-faculty@example.test", "faculty")
    other_faculty = add_user("other-schedule-faculty@example.test", "faculty")
    matching_student = add_user("schedule-student@example.test", "student", semester="2", section="B")
    different_student = add_user("different-schedule-student@example.test", "student", semester="3", section="A")
    application.supabase.table("faculty_sections").insert({"faculty_id": faculty["id"], "section": "B"}).execute()
    login_session(client, faculty)

    payload = {
        "subject": "Data Structures",
        "semester": "2",
        "section": "B",
        "day_of_week": "Tuesday",
        "starts_at": "09:00",
        "ends_at": "10:00",
        "room": "Lab 2",
    }
    created = client.post("/timetable/faculty", data=payload)
    assert created.status_code == 302
    entry = application.supabase.table("timetable_entries").select("*").eq("faculty_id", faculty["id"]).execute().data[0]

    overlap = {**payload, "subject": "Conflicting session", "starts_at": "09:30", "ends_at": "10:15"}
    assert client.post("/timetable/faculty", data=overlap).status_code == 409

    login_session(client, matching_student)
    assert b"Data Structures" in client.get("/timetable").data
    login_session(client, different_student)
    assert b"Data Structures" not in client.get("/timetable").data

    login_session(client, other_faculty)
    assert client.post(f"/timetable/faculty/{entry['id']}/delete").status_code == 302
    assert application.supabase.table("timetable_entries").select("id").eq("id", entry["id"]).execute().data


def test_coding_leaderboard_uses_real_student_points(client):
    current = add_user("leader-current@example.test", "student", points=40, roll_number="CB-02")
    add_user("leader-top@example.test", "student", points=125, roll_number="CB-01")
    login_session(client, current)

    response = client.get("/student%20leaderboard")
    assert response.status_code == 200
    assert b"CB-01" in response.data
    assert response.data.index(b"CB-01") < response.data.index(b"CB-02")
    assert b"Your rank in top 100" in response.data
    assert b"Alice Johnson" not in response.data


def test_code_submission_is_unavailable_without_execution_key(client, monkeypatch):
    student = add_user("coder@example.test", "student")
    login_session(client, student)
    monkeypatch.setitem(application.JUDGE0_API_HEADERS, "x-rapidapi-key", "")

    response = client.post("/submit", json={"problem_id": 1, "code": "print(1)", "language_id": 71})
    assert response.status_code == 503


def test_coding_challenge_awards_points_only_once(client, monkeypatch):
    student = add_user("points@example.test", "student", points=0)
    login_session(client, student)
    monkeypatch.setitem(application.JUDGE0_API_HEADERS, "x-rapidapi-key", "test-key")
    monkeypatch.setattr(application, "_execution_rate_limit", lambda: None)
    expected = {"[2,7,11,15]\n9\n": "[0,1]", "[3,2,4]\n6\n": "[1,2]", "[3,3]\n6\n": "[0,1]"}
    tokens = {}

    class FakeResponse:
        def __init__(self, body):
            self.body = body

        def raise_for_status(self):
            pass

        def json(self):
            return self.body

    def post(_url, **kwargs):
        token = str(len(tokens))
        tokens[token] = kwargs["json"]["stdin"]
        return FakeResponse({"token": token})

    def get(_url, **_kwargs):
        token = _url.rsplit("/", 1)[-1]
        return FakeResponse({"stdout": expected[tokens[token]], "status": {"id": 3, "description": "Accepted"}})

    monkeypatch.setattr(application.requests, "post", post)
    monkeypatch.setattr(application.requests, "get", get)
    payload = {"problem_id": 1, "code": "solution", "language_id": 71}

    first = client.post("/submit", json=payload).get_json()
    second = client.post("/submit", json=payload).get_json()
    points = application.supabase.table("users").select("points").eq("id", student["id"]).execute().data[0]["points"]
    assert first["points_earned"] == 100
    assert second["points_earned"] == 0 and second["already_solved"] is True
    assert points == 100


def test_database_adapter_rejects_untrusted_identifiers():
    with pytest.raises(ValueError):
        application.supabase.table("users; DROP TABLE users")
    with pytest.raises(ValueError):
        application.supabase.table("users").order("name; DROP TABLE users")


def test_cross_origin_writes_are_rejected(client):
    response = client.post("/login", data={"email": "a@example.test", "password": "incorrect"}, headers={"Origin": "https://attacker.example"})
    assert response.status_code == 403


def test_admin_delete_only_removes_student_accounts(client):
    admin = add_user("delete-admin@example.test", "admin")
    student = add_user("delete-student@example.test", "student", section="A")
    faculty = add_user("delete-faculty@example.test", "faculty")
    login_session(client, admin)

    assert client.delete(f"/delete_student/{faculty['id']}").status_code == 404
    assert client.delete(f"/delete_student/{student['id']}").status_code == 200
    assert application.supabase.table("users").select("id").eq("id", faculty["id"]).execute().data
    assert not application.supabase.table("users").select("id").eq("id", student["id"]).execute().data


def test_modern_cohere_response_extracts_text(monkeypatch):
    class FakeCohere:
        def chat(self, **kwargs):
            assert kwargs["messages"][0]["role"] == "user"
            return SimpleNamespace(message=SimpleNamespace(content=[SimpleNamespace(type="text", text="A safe review")]))

    monkeypatch.setattr(application, "co", FakeCohere())
    assert application.generate_with_cohere("review", max_tokens=20) == "A safe review"


def test_cpp_language_label_maps_to_judge0_id():
    assert application.LANGUAGE_IDS["c++"] == application.LANGUAGE_IDS["cpp"] == 54


def test_supabase_compat_translates_count_and_or_filters():
    class FakeQuery:
        def __init__(self):
            self.calls = []

        def __getattr__(self, name):
            def call(*args, **kwargs):
                self.calls.append((name, args, kwargs))
                return self
            return call

        def execute(self):
            return SimpleNamespace(data=[], count=4)

    class FakeClient:
        def __init__(self):
            self.query = FakeQuery()

        def table(self, _name):
            return self.query

    fake = FakeClient()
    compat = database.SupabaseCompatClient(fake)
    count = compat.table("users").select("count").execute()
    compat.table("chat_rooms").select("id").or_("user1_id = 7", "user2_id = 7").execute()

    assert count.data == [{"count": 4}]
    assert ("or_", ("user1_id.eq.7,user2_id.eq.7",), {}) in fake.query.calls


def test_all_templates_compile_and_role_pages_render(client):
    for template_name in application.app.jinja_env.list_templates():
        application.app.jinja_env.get_template(template_name)

    student = add_user("pages-student@example.test", "student", semester="1", section="A")
    faculty = add_user("pages-faculty@example.test", "faculty")
    admin = add_user("pages-admin@example.test", "admin")

    page_groups = [
        (student, ["/home", "/mycourse", "/compiler", "/attendance", "/coding_tracks", "/myverse", "/student/assignments", "/student_coding_assesment", "/chat", "/student%20leaderboard", "/change_password"]),
        (faculty, ["/faculty", "/faculty/attendance", "/faculty/assignments", "/faculty/coding_assessment", "/faculty_chat"]),
        (admin, ["/dashboard/admin", "/faculty/admin", "/students/admin", "/test-db"]),
    ]
    for user, paths in page_groups:
        login_session(client, user)
        for path in paths:
            assert client.get(path).status_code < 500, path
