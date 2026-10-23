"""
Database layer with a Supabase-compatible query API and a local SQLite mode.
"""
from __future__ import annotations

import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import bcrypt

DB_PATH = Path(os.environ.get("DATABASE_PATH", Path(__file__).resolve().parent / "campus_bridge.db")).expanduser()

# Public, non-personal starter content. This is deliberately separate from
# optional demo accounts and can safely be applied on every local startup.
COURSE_CATALOG = {
    1: [
        ("Programming Fundamentals", 8, 48, "CSE101", 4, "Foundational programming concepts, problem solving, and introductory software development."),
        ("Mathematics for Computing I", 6, 36, "MAT101", 3, "Core algebra, calculus, and mathematical reasoning for computing."),
        ("Digital Logic Design", 6, 36, "ECE101", 3, "Number systems, Boolean algebra, combinational logic, and digital circuits."),
    ],
    2: [
        ("Object-Oriented Programming", 8, 48, "CSE102", 4, "Classes, objects, inheritance, polymorphism, and robust application design."),
        ("Data Structures", 8, 48, "CSE103", 4, "Arrays, linked structures, trees, graphs, hashing, and algorithmic analysis."),
        ("Mathematics for Computing II", 6, 36, "MAT102", 3, "Discrete mathematics, probability, and linear algebra for computer science."),
    ],
    3: [
        ("Database Management Systems", 8, 48, "CSE201", 4, "Relational modeling, SQL, transactions, indexing, and database design."),
        ("Computer Organization", 7, 42, "CSE202", 3, "Processor architecture, instruction execution, memory, and input/output."),
        ("Design and Analysis of Algorithms", 8, 48, "CSE203", 4, "Algorithm design strategies, complexity, graph algorithms, and optimization."),
    ],
    4: [
        ("Operating Systems", 8, 48, "CSE204", 4, "Processes, concurrency, memory management, file systems, and scheduling."),
        ("Computer Networks", 8, 48, "CSE205", 4, "Network layers, routing, transport protocols, security, and distributed communication."),
        ("Software Engineering", 6, 36, "CSE206", 3, "Requirements, architecture, testing, delivery, and collaborative software practices."),
    ],
    5: [
        ("Web Application Engineering", 8, 48, "CSE301", 4, "Accessible interfaces, HTTP, APIs, server-side development, and deployment."),
        ("Theory of Computation", 7, 42, "CSE302", 3, "Automata, formal languages, computability, and complexity foundations."),
        ("Artificial Intelligence Foundations", 8, 48, "CSE303", 4, "Search, knowledge representation, reasoning, and introductory machine learning."),
    ],
    6: [
        ("Machine Learning", 8, 48, "CSE304", 4, "Data preparation, supervised learning, evaluation, and responsible model use."),
        ("Compiler Design", 7, 42, "CSE305", 3, "Lexical analysis, parsing, semantic checks, and code generation."),
        ("Cloud Computing", 6, 36, "CSE306", 3, "Cloud architecture, virtualization, distributed services, and reliability."),
    ],
    7: [
        ("Information Security", 7, 42, "CSE401", 3, "Security principles, cryptography, threat modeling, and secure development."),
        ("Distributed Systems", 8, 48, "CSE402", 4, "Coordination, consistency, fault tolerance, and scalable distributed services."),
        ("Capstone Project I", 6, 48, "CSE403", 3, "Project planning, research, prototyping, and iterative engineering practice."),
    ],
    8: [
        ("Data Engineering", 7, 42, "CSE404", 3, "Data pipelines, storage systems, quality, and analytics infrastructure."),
        ("Human-Computer Interaction", 6, 36, "CSE405", 3, "User research, interaction design, accessibility, and usability evaluation."),
        ("Capstone Project II", 8, 64, "CSE406", 4, "Build, validate, document, and present a complete software project."),
    ],
}


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")


def _validate_identifier(value: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError("Invalid SQL identifier")
    return value


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


class APIResponse:
    """Mimics supabase response objects (response.data)."""

    def __init__(self, data: Any = None):
        self.data = data if data is not None else []


class QueryBuilder:
    def __init__(self, client: "SQLiteClient", table: str):
        self.client = client
        self.table = _validate_identifier(table)
        self._select_cols: str = "*"
        self._filters: List[Tuple[str, str, Any]] = []
        self._or_clauses: List[str] = []
        self._order: Optional[Tuple[str, bool]] = None
        self._limit: Optional[int] = None
        self._operation: str = "select"
        self._payload: Any = None
        self._count_mode = False
        self._nested: List[Dict[str, Any]] = []

    def select(self, *columns: str) -> "QueryBuilder":
        self._operation = "select"
        if not columns:
            self._select_cols = "*"
            return self

        # Join multi-arg or single multi-line select strings
        raw = ", ".join(columns)
        raw = re.sub(r"\s+", " ", raw).strip()

        if raw.strip() == "count":
            self._count_mode = True
            self._select_cols = "COUNT(*) AS count"
            return self

        # Detect PostgREST-style nested selects and strip them for the base query
        nested_pattern = re.compile(
            r"(?P<alias>\w+)\s*:\s*(?P<table>\w+)(?:!\w+)?\s*\((?P<inner>[^)]*(?:\([^)]*\)[^)]*)*)\)",
            re.DOTALL,
        )
        for match in nested_pattern.finditer(raw):
            self._nested.append(
                {
                    "alias": match.group("alias"),
                    "table": match.group("table"),
                    "inner": match.group("inner").strip(),
                }
            )
        # Remove nested fragments from column list
        cleaned = nested_pattern.sub("", raw)
        cleaned = cleaned.replace("\n", " ")
        parts = [p.strip() for p in cleaned.split(",") if p.strip() and p.strip() != "*"]
        if "*" in cleaned or not parts:
            self._select_cols = "*"
        else:
            # Quote reserved / keep simple identifiers
            safe = []
            for p in parts:
                if re.match(r"^[\w.]+$", p):
                    safe.append(_validate_identifier(p))
                else:
                    raise ValueError("Invalid selected column")
            self._select_cols = ", ".join(safe) if safe else "*"
        return self

    def eq(self, column: str, value: Any) -> "QueryBuilder":
        self._filters.append((_validate_identifier(column), "=", value))
        return self

    def neq(self, column: str, value: Any) -> "QueryBuilder":
        self._filters.append((_validate_identifier(column), "!=", value))
        return self

    def in_(self, column: str, values: List[Any]) -> "QueryBuilder":
        self._filters.append((_validate_identifier(column), "IN", list(values)))
        return self

    def filter(self, column: str, operator: str, value: Any) -> "QueryBuilder":
        op = operator.lower()
        _validate_identifier(column)
        if op == "ilike":
            # SQLite LIKE is case-insensitive for ASCII by default with NOCASE
            self._filters.append((column, "LIKE", value))
        elif op == "like":
            self._filters.append((column, "LIKE", value))
        elif op == "neq":
            self._filters.append((column, "!=", value))
        elif op == "eq":
            self._filters.append((column, "=", value))
        elif op in {"lt", "lte", "gt", "gte"}:
            self._filters.append((column, {"lt": "<", "lte": "<=", "gt": ">", "gte": ">="}[op], value))
        else:
            raise ValueError("Unsupported filter operator")
        return self

    def or_(self, *conditions: str) -> "QueryBuilder":
        # Accepts strings like "user1_id = 1"
        self._or_clauses.extend(conditions)
        return self

    def order(self, column: str, desc: bool = False) -> "QueryBuilder":
        self._order = (_validate_identifier(column), bool(desc))
        return self

    def limit(self, n: int) -> "QueryBuilder":
        limit = int(n)
        if not 0 <= limit <= 10000:
            raise ValueError("Limit must be between 0 and 10000")
        self._limit = limit
        return self

    def insert(self, data: Union[Dict, List[Dict]]) -> "QueryBuilder":
        self._operation = "insert"
        self._payload = data
        return self

    def update(self, data: Dict) -> "QueryBuilder":
        self._operation = "update"
        self._payload = data
        return self

    def delete(self) -> "QueryBuilder":
        self._operation = "delete"
        return self

    def _where_sql(self) -> Tuple[str, List[Any]]:
        clauses: List[str] = []
        params: List[Any] = []
        for col, op, val in self._filters:
            if op == "IN":
                if not val:
                    clauses.append("0")
                    continue
                placeholders = ", ".join("?" * len(val))
                clauses.append(f"{col} IN ({placeholders})")
                params.extend(val)
            else:
                clauses.append(f"{col} {op} ?")
                params.append(val)
        if self._or_clauses:
            # Sanitize simple "col = value" / "col = N" forms
            safe_ors = []
            for c in self._or_clauses:
                m = re.match(r"^\s*(\w+)\s*=\s*(.+?)\s*$", c)
                if m:
                    column = _validate_identifier(m.group(1))
                    safe_ors.append(f"{column} = ?")
                    raw_val = m.group(2).strip().strip("'\"")
                    try:
                        params.append(int(raw_val))
                    except ValueError:
                        params.append(raw_val)
            if safe_ors:
                clauses.append("(" + " OR ".join(safe_ors) + ")")
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        return where, params

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        # Normalize SQLite 0/1 bool-ish columns used by the app
        for key in ("is_active", "is_online"):
            if key in d and d[key] is not None:
                d[key] = bool(d[key])
        return d

    def _fk_column(self, parent_table: str, child_table: str, alias: str) -> str:
        """Guess foreign key column linking child rows to parent."""
        # Common patterns used in this app
        guesses = [
            f"{parent_table.rstrip('s')}_id",
            f"{alias}_id" if alias.endswith("s") is False else None,
            "room_id",
            "assessment_id",
            "faculty_id",
            "user_id",
            "student_id",
        ]
        # Prefer parent-based name
        preferred = {
            ("code_rooms", "code_room_participants"): "room_id",
            ("code_rooms", "code_room_messages"): "room_id",
            ("code_room_participants", "users"): "user_id",
            ("code_room_messages", "users"): "user_id",
            ("coding_assessments", "users"): "faculty_id",
            ("assessments", "assessment_links"): "assessment_id",
            ("assessments", "assignment_submissions"): "assessment_id",
        }
        if (parent_table, child_table) in preferred:
            return preferred[(parent_table, child_table)]
        for g in guesses:
            if g:
                return g
        return "id"

    def _attach_nested(self, conn: sqlite3.Connection, rows: List[Dict]) -> None:
        if not self._nested or not rows:
            return
        parent_ids = [r["id"] for r in rows if "id" in r]
        for nest in self._nested:
            alias = nest["alias"]
            child_table = nest["table"]
            inner = nest["inner"]

            # Nested-within-nested: e.g. *, user:users(name)
            inner_nested = []
            inner_pattern = re.compile(
                r"(?P<alias>\w+)\s*:\s*(?P<table>\w+)(?:!\w+)?\s*\((?P<inner>[^)]*)\)"
            )
            for m in inner_pattern.finditer(inner):
                inner_nested.append(
                    {
                        "alias": m.group("alias"),
                        "table": m.group("table"),
                        "inner": m.group("inner").strip(),
                    }
                )
            inner_clean = inner_pattern.sub("", inner)
            inner_cols = [c.strip() for c in inner_clean.split(",") if c.strip()]
            _validate_identifier(alias)
            _validate_identifier(child_table)
            for nested in inner_nested:
                _validate_identifier(nested["alias"])
                _validate_identifier(nested["table"])
            if not inner_cols or "*" in inner_cols:
                select_inner = "*"
            else:
                select_inner = ", ".join(_validate_identifier(c) for c in inner_cols)

            # Many-to-one (belongs_to): alias singular-ish pointing at users via faculty_id / user_id
            belongs_to = child_table == "users" and alias in ("user", "faculty")
            if belongs_to:
                for row in rows:
                    if alias == "faculty":
                        fk_val = row.get("faculty_id")
                    else:
                        fk_val = row.get("user_id") or row.get("sender_id")
                    if fk_val is None:
                        row[alias] = None
                        continue
                    cur = conn.execute(
                        f"SELECT {select_inner} FROM {child_table} WHERE id = ?",
                        (fk_val,),
                    )
                    related = cur.fetchone()
                    row[alias] = self._row_to_dict(related) if related else None
                continue

            # One-to-many: collect children keyed by FK to parent
            fk = _validate_identifier(self._fk_column(self.table, child_table, alias))
            if not parent_ids:
                for row in rows:
                    row[alias] = []
                continue
            placeholders = ", ".join("?" * len(parent_ids))
            cur = conn.execute(
                f"SELECT {select_inner} FROM {child_table} WHERE {fk} IN ({placeholders})",
                parent_ids,
            )
            children = [self._row_to_dict(r) for r in cur.fetchall()]

            # Attach deeper nested (e.g. user on participants)
            if inner_nested:
                for nest2 in inner_nested:
                    a2, t2, i2 = nest2["alias"], nest2["table"], nest2["inner"]
                    _validate_identifier(a2)
                    _validate_identifier(t2)
                    cols2 = [c.strip() for c in i2.split(",") if c.strip()]
                    sel2 = "*" if not cols2 or "*" in cols2 else ", ".join(_validate_identifier(c) for c in cols2)
                    for child in children:
                        if t2 == "users":
                            fk_val = child.get("user_id") or child.get("sender_id")
                        else:
                            fk_val = child.get(f"{a2}_id")
                        if fk_val is None:
                            child[a2] = None
                            continue
                        c2 = conn.execute(f"SELECT {sel2} FROM {t2} WHERE id = ?", (fk_val,))
                        related = c2.fetchone()
                        child[a2] = self._row_to_dict(related) if related else None

            by_parent: Dict[Any, List] = {}
            for child in children:
                by_parent.setdefault(child.get(fk), []).append(child)
            for row in rows:
                row[alias] = by_parent.get(row.get("id"), [])

    def execute(self) -> APIResponse:
        conn = _get_connection()
        try:
            if self._operation == "select":
                where, params = self._where_sql()
                sql = f"SELECT {self._select_cols} FROM {self.table}{where}"
                if self._order:
                    col, desc = self._order
                    sql += f" ORDER BY {col} {'DESC' if desc else 'ASC'}"
                if self._limit is not None:
                    sql += f" LIMIT {int(self._limit)}"
                cur = conn.execute(sql, params)
                if self._count_mode:
                    count = cur.fetchone()["count"]
                    return APIResponse([{"count": count}])
                rows = [self._row_to_dict(r) for r in cur.fetchall()]
                self._attach_nested(conn, rows)
                return APIResponse(rows)

            if self._operation == "insert":
                items = self._payload if isinstance(self._payload, list) else [self._payload]
                result_rows = []
                for item in items:
                    data = dict(item)
                    if not data:
                        raise ValueError("Insert data cannot be empty")
                    for key in data:
                        _validate_identifier(key)
                    # Replace Supabase-style now() sentinel
                    for k, v in list(data.items()):
                        if v == "now()":
                            data[k] = _utcnow()
                        elif isinstance(v, bool):
                            data[k] = int(v)
                    if "created_at" not in data and self._has_column(conn, "created_at"):
                        data["created_at"] = _utcnow()
                    cols = ", ".join(data.keys())
                    placeholders = ", ".join("?" * len(data))
                    cur = conn.execute(
                        f"INSERT INTO {self.table} ({cols}) VALUES ({placeholders})",
                        list(data.values()),
                    )
                    row_id = cur.lastrowid
                    fetched = conn.execute(
                        f"SELECT * FROM {self.table} WHERE id = ?", (row_id,)
                    ).fetchone()
                    if fetched:
                        result_rows.append(self._row_to_dict(fetched))
                conn.commit()
                return APIResponse(result_rows)

            if self._operation == "update":
                data = dict(self._payload)
                if not data:
                    raise ValueError("Update data cannot be empty")
                for key in data:
                    _validate_identifier(key)
                for k, v in list(data.items()):
                    if v == "now()":
                        data[k] = _utcnow()
                    elif isinstance(v, bool):
                        data[k] = int(v)
                where, params = self._where_sql()
                if not where:
                    raise ValueError("Refusing to UPDATE without a WHERE clause")
                set_clause = ", ".join(f"{k} = ?" for k in data.keys())
                # Fetch matching ids first so we can return updated rows
                id_rows = conn.execute(f"SELECT id FROM {self.table}{where}", params).fetchall()
                ids = [r["id"] for r in id_rows]
                conn.execute(
                    f"UPDATE {self.table} SET {set_clause}{where}",
                    list(data.values()) + params,
                )
                conn.commit()
                if not ids:
                    return APIResponse([])
                placeholders = ", ".join("?" * len(ids))
                cur = conn.execute(
                    f"SELECT * FROM {self.table} WHERE id IN ({placeholders})", ids
                )
                return APIResponse([self._row_to_dict(r) for r in cur.fetchall()])

            if self._operation == "delete":
                where, params = self._where_sql()
                if not where:
                    raise ValueError("Refusing to DELETE without a WHERE clause")
                existing = conn.execute(
                    f"SELECT * FROM {self.table}{where}", params
                ).fetchall()
                rows = [self._row_to_dict(r) for r in existing]
                conn.execute(f"DELETE FROM {self.table}{where}", params)
                conn.commit()
                return APIResponse(rows)

            return APIResponse([])
        finally:
            conn.close()

    def _has_column(self, conn: sqlite3.Connection, column: str) -> bool:
        _validate_identifier(column)
        cur = conn.execute(f"PRAGMA table_info({self.table})")
        return any(row["name"] == column for row in cur.fetchall())


class SQLiteClient:
    def table(self, name: str) -> QueryBuilder:
        return QueryBuilder(self, name)

    def rpc(self, fn_name: str, params: Optional[Dict] = None):
        """Stub for former Supabase RPC helpers (schema is created at startup)."""

        class _RpcBuilder:
            def execute(self) -> APIResponse:
                return APIResponse([{"ok": True, "function": fn_name}])

        return _RpcBuilder()


class SupabaseQueryCompat:
    """Keep the legacy route query shape while delegating to PostgREST."""

    def __init__(self, query):
        self.query = query
        self.count_mode = False

    def select(self, *columns):
        if len(columns) == 1 and columns[0].strip().lower() == "count":
            self.query = self.query.select("*", count="exact")
            self.count_mode = True
        else:
            self.query = self.query.select(", ".join(columns) if columns else "*")
        return self

    def eq(self, column, value):
        self.query = self.query.eq(column, value)
        return self

    def neq(self, column, value):
        self.query = self.query.neq(column, value)
        return self

    def in_(self, column, values):
        self.query = self.query.in_(column, values)
        return self

    def filter(self, column, operator, value):
        self.query = self.query.filter(column, operator, value)
        return self

    def order(self, column, desc=False):
        self.query = self.query.order(column, desc=desc)
        return self

    def limit(self, count):
        self.query = self.query.limit(count)
        return self

    def or_(self, *conditions):
        clauses = []
        for condition in conditions:
            match = re.fullmatch(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(\d+)\s*", condition)
            if not match:
                raise ValueError("Unsupported PostgREST OR expression")
            clauses.append(f"{match.group(1)}.eq.{match.group(2)}")
        self.query = self.query.or_(",".join(clauses))
        return self

    def insert(self, data):
        self.query = self.query.insert(data)
        return self

    def update(self, data):
        self.query = self.query.update(data)
        return self

    def delete(self):
        self.query = self.query.delete()
        return self

    def execute(self):
        response = self.query.execute()
        if self.count_mode:
            return APIResponse([{"count": response.count or 0}])
        return APIResponse(response.data or [])


class SupabaseCompatClient:
    def __init__(self, client):
        self.client = client

    def table(self, name):
        return SupabaseQueryCompat(self.client.table(name))

    def rpc(self, name, params=None):
        return SupabaseQueryCompat(self.client.rpc(name, params or {}))


SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
USING_SUPABASE = bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)
if USING_SUPABASE:
    try:
        from supabase import create_client
    except ImportError as exc:
        raise RuntimeError("Install the supabase package to use the configured Supabase backend") from exc
    supabase = SupabaseCompatClient(create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY))
else:
    supabase = SQLiteClient()


def init_db() -> None:
    if USING_SUPABASE:
        # Apply supabase_schema.sql once in the Supabase SQL editor for the
        # additive tables; application startup must not mutate remote schema.
        return
    conn = _get_connection()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                name TEXT,
                role TEXT NOT NULL,
                roll_number TEXT,
                branch TEXT,
                section TEXT,
                semester TEXT,
                subject TEXT,
                points INTEGER DEFAULT 0,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                section TEXT,
                attended_classes INTEGER DEFAULT 0,
                total_classes INTEGER DEFAULT 0,
                FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS attendance_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                section TEXT NOT NULL,
                faculty_id INTEGER NOT NULL,
                attendance_date TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('present', 'absent')),
                UNIQUE(student_id, section, attendance_date),
                FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (faculty_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS assessment_solutions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                assessment_id INTEGER NOT NULL,
                solved_at TEXT NOT NULL,
                UNIQUE(user_id, assessment_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS problem_solutions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                problem_id INTEGER NOT NULL,
                solved_at TEXT NOT NULL,
                UNIQUE(user_id, problem_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS faculty_sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                faculty_id INTEGER NOT NULL,
                section TEXT NOT NULL,
                FOREIGN KEY (faculty_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                code TEXT,
                faculty_id INTEGER,
                description TEXT,
                created_at TEXT,
                FOREIGN KEY (faculty_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS timetable_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                faculty_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                semester INTEGER NOT NULL CHECK(semester BETWEEN 1 AND 8),
                section TEXT NOT NULL,
                day_of_week TEXT NOT NULL CHECK(day_of_week IN ('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday')),
                starts_at TEXT NOT NULL,
                ends_at TEXT NOT NULL,
                room TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (faculty_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS timetable_entries_group_idx
                ON timetable_entries (semester, section, day_of_week, starts_at);
            CREATE INDEX IF NOT EXISTS timetable_entries_faculty_idx
                ON timetable_entries (faculty_id, day_of_week, starts_at);

            CREATE TABLE IF NOT EXISTS assessments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                faculty_id INTEGER,
                subject TEXT,
                year TEXT,
                branch TEXT,
                description TEXT,
                deadline TEXT,
                created_at TEXT,
                FOREIGN KEY (faculty_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS assessment_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assessment_id INTEGER,
                link_type TEXT,
                link_url TEXT,
                description TEXT,
                FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS assignment_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assessment_id INTEGER,
                name TEXT,
                roll_number TEXT,
                link TEXT,
                created_at TEXT,
                FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS coding_assessments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                faculty_id INTEGER,
                title TEXT,
                description TEXT,
                input_format TEXT,
                output_format TEXT,
                difficulty TEXT,
                points INTEGER DEFAULT 0,
                time_limit INTEGER,
                memory_limit INTEGER,
                allowed_languages TEXT,
                created_at TEXT,
                FOREIGN KEY (faculty_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS assessment_test_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assessment_id INTEGER,
                input_data TEXT,
                expected_output TEXT,
                FOREIGN KEY (assessment_id) REFERENCES coding_assessments(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS code_rooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                created_by INTEGER,
                language TEXT,
                code TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1,
                created_at TEXT,
                FOREIGN KEY (created_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS code_room_participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id INTEGER,
                user_id INTEGER,
                is_online INTEGER DEFAULT 1,
                FOREIGN KEY (room_id) REFERENCES code_rooms(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS code_room_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id INTEGER,
                user_id INTEGER,
                sender_id INTEGER,
                message TEXT,
                created_at TEXT,
                FOREIGN KEY (room_id) REFERENCES code_rooms(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS chat_rooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user1_id INTEGER,
                user2_id INTEGER,
                created_at TEXT,
                FOREIGN KEY (user1_id) REFERENCES users(id),
                FOREIGN KEY (user2_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id INTEGER,
                sender_id INTEGER,
                message TEXT,
                created_at TEXT,
                FOREIGN KEY (room_id) REFERENCES chat_rooms(id) ON DELETE CASCADE
            );
            """
        )

        # Semester course tables (semester1 … semester8)
        # Columns match templates/mycourse.html (subject, modules, hours, pdf_link)
        for n in range(1, 9):
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS semester{n} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject TEXT,
                    modules INTEGER,
                    hours INTEGER,
                    pdf_link TEXT,
                    course_code TEXT,
                    credits INTEGER,
                    faculty TEXT,
                    description TEXT
                )
                """
            )

        _seed_course_catalog(conn)
        conn.commit()
        _seed_if_empty(conn)
    finally:
        conn.close()


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _seed_course_catalog(conn: sqlite3.Connection) -> None:
    """Insert missing public catalog rows without changing existing records."""
    for semester, courses in COURSE_CATALOG.items():
        table = f"semester{semester}"
        for subject, modules, hours, code, credits, description in courses:
            conn.execute(
                f"""INSERT INTO {table} (subject, modules, hours, pdf_link, course_code, credits, faculty, description)
                    SELECT ?, ?, ?, '', ?, ?, 'Campus Bridge', ?
                    WHERE NOT EXISTS (SELECT 1 FROM {table} WHERE course_code = ?)""",
                (subject, modules, hours, code, credits, description, code),
            )


def _seed_if_empty(conn: sqlite3.Connection) -> None:
    count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    if count > 0:
        return

    if os.environ.get("SEED_DEMO_DATA", "").strip().lower() not in {"1", "true", "yes"}:
        return

    demo_password = os.environ.get("DEMO_PASSWORD", "")
    if len(demo_password) < 12:
        raise ValueError("DEMO_PASSWORD must contain at least 12 characters when demo seeding is enabled")

    now = _utcnow()
    pw = _hash(demo_password)

    users = [
        ("admin@gmail.com", pw, "Admin", "admin", None, None, None, None, None, 0, now),
        ("faculty@gmail.com", pw, "john", "faculty", "FAC001", "CSE", None, None, "Programming", 0, now),
        ("23102a040719@mbu.asia", pw, "sunny", "student", "23102A040719", "CSE", "A", "1", None, 0, now),
        ("raghs@gmail.com", pw, "raghs", "student", "23102A040001", "CSE", "A", "1", None, 0, now),
    ]
    conn.executemany(
        """
        INSERT INTO users (email, password, name, role, roll_number, branch, section, semester, subject, points, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        users,
    )

    faculty_id = conn.execute(
        "SELECT id FROM users WHERE email = ?", ("faculty@gmail.com",)
    ).fetchone()["id"]
    conn.execute(
        "INSERT INTO faculty_sections (faculty_id, section) VALUES (?, ?)",
        (faculty_id, "A"),
    )

    for email in ("23102a040719@mbu.asia", "raghs@gmail.com"):
        sid = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()["id"]
        conn.execute(
            """
            INSERT INTO attendance (student_id, section, attended_classes, total_classes)
            VALUES (?, 'A', 0, 0)
            """,
            (sid,),
        )

    conn.executemany(
        """
        INSERT INTO courses (name, code, faculty_id, description, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            ("Programming Fundamentals", "CSE101", faculty_id, "Intro to programming", now),
            ("Mathematics I", "MAT101", faculty_id, "Calculus and algebra", now),
            ("Digital Logic", "ECE101", faculty_id, "Boolean algebra and circuits", now),
        ],
    )
    conn.commit()


# Singleton used by the Flask app
