import os
import hmac
import hashlib
import secrets
from datetime import date, timedelta, datetime
from io import BytesIO

import pandas as pd
import streamlit as st
from sqlalchemy import (
    create_engine, String, Integer, Date, DateTime, ForeignKey, Text, select,
    func, or_
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, relationship

# -------------------- Page setup --------------------
st.set_page_config(
    page_title="LibraDesk | Library Management",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_NAME = "LibraDesk"

def setting(name, default=""):
    value = os.getenv(name, "").strip()
    if value:
        return value
    try:
        value = str(st.secrets.get(name, "")).strip()
    except Exception:
        value = ""
    return value or default

FINE_PER_DAY = int(setting("FINE_PER_DAY", "5"))
LOAN_DAYS = int(setting("LOAN_DAYS", "14"))

# -------------------- Database --------------------
def get_database_url():
    """Use a hosted PostgreSQL URL when configured; otherwise use local SQLite."""
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        try:
            url = st.secrets.get("DATABASE_URL", "").strip()
        except Exception:
            url = ""
    if url:
        # Supabase and some providers give postgres:// or postgresql:// URLs.
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://") and "+psycopg" not in url:
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url
    return "sqlite:///library.db"

DATABASE_URL = get_database_url()

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="member", nullable=False)
    active: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Book(Base):
    __tablename__ = "books"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    isbn: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(240), index=True, nullable=False)
    author: Mapped[str] = mapped_column(String(180), nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="General", nullable=False)
    publisher: Mapped[str] = mapped_column(String(180), default="", nullable=False)
    published_year: Mapped[int] = mapped_column(Integer, default=2024, nullable=False)
    total_copies: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Member(Base):
    __tablename__ = "members"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    member_code: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    department: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    joined_on: Mapped[date] = mapped_column(Date, default=date.today)
    active: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

class Loan(Base):
    __tablename__ = "loans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), nullable=False)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False)
    issued_on: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    due_on: Mapped[date] = mapped_column(Date, nullable=False)
    returned_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    fine_paid: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    book: Mapped[Book] = relationship()
    member: Mapped[Member] = relationship()

@st.cache_resource
def get_engine(url):
    kwargs = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)

engine = get_engine(DATABASE_URL)
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

# -------------------- Password helpers --------------------
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260_000)
    return salt.hex() + ":" + digest.hex()

def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split(":", 1)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), 260_000)
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False

def seed_database():
    with SessionLocal() as db:
        admin_email = setting("ADMIN_EMAIL", "admin@library.local").strip().lower()
        admin_password = setting("ADMIN_PASSWORD", "ChangeMe123!")
        admin = db.scalar(select(User).where(User.email == admin_email))
        if admin is None:
            db.add(User(name="Library Administrator", email=admin_email,
                        password_hash=hash_password(admin_password), role="admin"))
        if db.scalar(select(func.count(Book.id))) == 0:
            samples = [
                ("9780132350884", "Clean Code", "Robert C. Martin", "Programming", "Prentice Hall", 2008, 4),
                ("9780262033848", "Introduction to Algorithms", "Thomas H. Cormen et al.", "Computer Science", "MIT Press", 2009, 3),
                ("9780131103627", "The C Programming Language", "Brian W. Kernighan", "Programming", "Prentice Hall", 1988, 2),
                ("9780062315007", "The Alchemist", "Paulo Coelho", "Fiction", "HarperOne", 2014, 3),
                ("9780140449136", "The Republic", "Plato", "Philosophy", "Penguin Classics", 2007, 2),
            ]
            for isbn, title, author, category, publisher, year, copies in samples:
                db.add(Book(isbn=isbn, title=title, author=author, category=category,
                            publisher=publisher, published_year=year, total_copies=copies))
        if db.scalar(select(func.count(Member.id))) == 0:
            db.add_all([
                Member(member_code="MEM001", name="Aarav Sharma", email="aarav@example.com",
                       phone="9000000001", department="Computer Science"),
                Member(member_code="MEM002", name="Priya Patil", email="priya@example.com",
                       phone="9000000002", department="Commerce"),
                Member(member_code="MEM003", name="Rohan Jadhav", email="rohan@example.com",
                       phone="9000000003", department="Science"),
            ])
        db.commit()

seed_database()

# -------------------- Business logic --------------------
def available_copies(db, book_id):
    book = db.get(Book, book_id)
    if not book:
        return 0
    active_loans = db.scalar(select(func.count(Loan.id)).where(
        Loan.book_id == book_id, Loan.returned_on.is_(None)
    )) or 0
    return max(0, book.total_copies - active_loans)

def current_fine(due_on, returned_on=None):
    end_date = returned_on or date.today()
    return max(0, (end_date - due_on).days) * FINE_PER_DAY

def money(value):
    return f"₹{int(value):,}"

def load_dashboard_data(db):
    total_titles = db.scalar(select(func.count(Book.id))) or 0
    total_copies = db.scalar(select(func.coalesce(func.sum(Book.total_copies), 0))) or 0
    members = db.scalar(select(func.count(Member.id)).where(Member.active == 1)) or 0
    active_loans = db.scalar(select(func.count(Loan.id)).where(Loan.returned_on.is_(None))) or 0
    overdue = db.scalar(select(func.count(Loan.id)).where(
        Loan.returned_on.is_(None), Loan.due_on < date.today()
    )) or 0
    return total_titles, total_copies, members, active_loans, overdue

def safe_commit(db):
    try:
        db.commit()
        return True
    except Exception as exc:
        db.rollback()
        st.error(f"Could not save the change. Check for duplicate ISBN/member code/email. Details: {exc}")
        return False

def csv_download(df, filename, label):
    st.download_button(label, data=df.to_csv(index=False).encode("utf-8-sig"),
                       file_name=filename, mime="text/csv", use_container_width=False)

# -------------------- Styling --------------------
st.markdown("""
<style>
    .stApp { background: #f5f7fb; }
    [data-testid="stSidebar"] { background: #101827; }
    [data-testid="stSidebar"] * { color: #f8fafc !important; }
    .hero { padding: 1.25rem 1.5rem; border-radius: 18px; color: white;
            background: linear-gradient(115deg, #172554, #2563eb 65%, #38bdf8);
            margin-bottom: 1rem; }
    .hero h1 { color: white; margin-bottom: .2rem; }
    .hero p { color: #e0f2fe; margin-bottom: 0; }
    div[data-testid="stMetric"] { background: white; border: 1px solid #e2e8f0;
            padding: 14px; border-radius: 14px; }
    .small-muted { color: #64748b; font-size: .9rem; }
    div.stButton > button { border-radius: 9px; }
</style>
""", unsafe_allow_html=True)

# -------------------- Login --------------------
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "login_notice" not in st.session_state:
    st.session_state.login_notice = ""

def login_screen():
    left, center, right = st.columns([1, 1.15, 1])
    with center:
        st.markdown('<div class="hero"><h1>📚 LibraDesk</h1><p>Library operations, made simple.</p></div>', unsafe_allow_html=True)
        st.subheader("Sign in")
        st.caption("Access the library dashboard using your account.")
        with st.form("login_form"):
            email = st.text_input("Email address", placeholder="admin@library.local")
            password = st.text_input("Password", type="password", placeholder="Enter password")
            submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
        if submitted:
            with SessionLocal() as db:
                user = db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))
                if user and user.active == 1 and verify_password(password, user.password_hash):
                    st.session_state.user_id = user.id
                    st.session_state.user_name = user.name
                    st.session_state.user_role = user.role
                    st.session_state.user_email = user.email
                    st.rerun()
                else:
                    st.error("Incorrect email or password, or the account is inactive.")
        st.info("First run demo admin: `admin@library.local` / `ChangeMe123!`. Change this before deploying publicly by setting ADMIN_EMAIL and ADMIN_PASSWORD.")
        st.caption("For a college demo, use fictional sample records. Do not upload real student data to a public demo.")
login_screen() if st.session_state.user_id is None else None

if st.session_state.user_id is None:
    st.stop()

# -------------------- Sidebar/navigation --------------------
with st.sidebar:
    st.markdown(f"# 📚 {APP_NAME}")
    st.caption("Library Management Portal")
    st.divider()
    st.write(f"Signed in as **{st.session_state.user_name}**")
    st.caption(f"Role: {st.session_state.user_role.title()}")
    pages = ["Dashboard", "Book Catalog", "Issue / Return", "Members", "Reports"]
    if st.session_state.user_role == "admin":
        pages += ["User Accounts", "Settings"]
    page = st.radio("Navigation", pages, label_visibility="collapsed")
    st.divider()
    if st.button("Log out", use_container_width=True):
        for key in ["user_id", "user_name", "user_role", "user_email"]:
            st.session_state.pop(key, None)
        st.rerun()
    st.caption("BCS Final-Year Project")

with SessionLocal() as db:
    # -------------------- Dashboard --------------------
    if page == "Dashboard":
        st.markdown('<div class="hero"><h1>Library Dashboard</h1><p>Overview of books, members, circulation and overdue returns.</p></div>', unsafe_allow_html=True)
        titles, copies, members, active_loans, overdue = load_dashboard_data(db)
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Book titles", f"{titles:,}")
        c2.metric("Total copies", f"{copies:,}")
        c3.metric("Active members", f"{members:,}")
        c4.metric("Books on loan", f"{active_loans:,}")
        c5.metric("Overdue loans", f"{overdue:,}", delta=f"{overdue} need attention" if overdue else "All clear",
                  delta_color="inverse")
        st.subheader("Recent circulation")
        loans = db.scalars(select(Loan).order_by(Loan.id.desc()).limit(8)).all()
        if loans:
            rows = []
            for loan in loans:
                rows.append({"Loan ID": loan.id, "Book": loan.book.title, "Member": loan.member.name,
                             "Issued": loan.issued_on, "Due": loan.due_on,
                             "Status": "Returned" if loan.returned_on else ("Overdue" if loan.due_on < date.today() else "On loan"),
                             "Fine": money(current_fine(loan.due_on, loan.returned_on))})
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No borrowing transactions yet. Use Issue / Return to create the first loan.")
        st.subheader("Books by category")
        category_rows = db.execute(select(Book.category, func.sum(Book.total_copies)).group_by(Book.category)).all()
        if category_rows:
            st.bar_chart(pd.DataFrame(category_rows, columns=["Category", "Copies"]).set_index("Category"))
        st.caption(f"Fine policy: {money(FINE_PER_DAY)} per overdue day · Standard loan period: {LOAN_DAYS} days")

    # -------------------- Book catalog --------------------
    elif page == "Book Catalog":
        st.title("📖 Book Catalog")
        st.caption("Search the catalog, check availability, and maintain book records.")
        search = st.text_input("Search by title, author, ISBN or category", key="book_search")
        query = select(Book).order_by(Book.title)
        if search.strip():
            pattern = f"%{search.strip()}%"
            query = query.where(or_(Book.title.ilike(pattern), Book.author.ilike(pattern),
                                    Book.isbn.ilike(pattern), Book.category.ilike(pattern)))
        books = db.scalars(query).all()
        book_rows = []
        for b in books:
            book_rows.append({"ID": b.id, "ISBN": b.isbn, "Title": b.title, "Author": b.author,
                              "Category": b.category, "Year": b.published_year,
                              "Total copies": b.total_copies, "Available": available_copies(db, b.id)})
        if book_rows:
            st.dataframe(pd.DataFrame(book_rows), use_container_width=True, hide_index=True)
            csv_download(pd.DataFrame(book_rows), "book_catalog.csv", "⬇ Export catalog CSV")
        else:
            st.info("No books match your search.")
        if st.session_state.user_role == "admin":
            st.divider()
            st.subheader("Add a book")
            with st.form("add_book_form", clear_on_submit=True):
                col1, col2 = st.columns(2)
                isbn = col1.text_input("ISBN *")
                title = col2.text_input("Book title *")
                author = col1.text_input("Author *")
                category = col2.selectbox("Category", ["Programming", "Computer Science", "Fiction", "Science", "Commerce", "History", "Philosophy", "General", "Other"])
                publisher = col1.text_input("Publisher")
                year = col2.number_input("Publication year", min_value=1000, max_value=2100, value=2024)
                copies = st.number_input("Total copies", min_value=1, max_value=10000, value=1)
                add_book = st.form_submit_button("Add book", type="primary")
            if add_book:
                if not isbn.strip() or not title.strip() or not author.strip():
                    st.error("ISBN, title and author are required.")
                elif db.scalar(select(Book).where(Book.isbn == isbn.strip())):
                    st.error("A book with this ISBN already exists.")
                else:
                    db.add(Book(isbn=isbn.strip(), title=title.strip(), author=author.strip(),
                                category=category, publisher=publisher.strip(),
                                published_year=int(year), total_copies=int(copies)))
                    if safe_commit(db):
                        st.success("Book added successfully.")
                        st.rerun()
            st.subheader("Edit or remove a book")
            if books:
                chosen = st.selectbox("Choose book", books, format_func=lambda b: f"{b.title} — {b.isbn}", key="edit_book_choice")
                with st.form("edit_book_form"):
                    ec1, ec2 = st.columns(2)
                    e_title = ec1.text_input("Title", value=chosen.title)
                    e_author = ec2.text_input("Author", value=chosen.author)
                    e_category = ec1.text_input("Category", value=chosen.category)
                    e_publisher = ec2.text_input("Publisher", value=chosen.publisher)
                    e_year = ec1.number_input("Year", min_value=1000, max_value=2100, value=chosen.published_year)
                    e_copies = ec2.number_input("Total copies", min_value=1, max_value=10000, value=chosen.total_copies)
                    save_book = st.form_submit_button("Save changes")
                if save_book:
                    active_count = db.scalar(select(func.count(Loan.id)).where(Loan.book_id == chosen.id, Loan.returned_on.is_(None))) or 0
                    if int(e_copies) < active_count:
                        st.error(f"Total copies cannot be below active loans ({active_count}).")
                    elif not e_title.strip() or not e_author.strip():
                        st.error("Title and author cannot be blank.")
                    else:
                        chosen.title, chosen.author = e_title.strip(), e_author.strip()
                        chosen.category, chosen.publisher = e_category.strip(), e_publisher.strip()
                        chosen.published_year, chosen.total_copies = int(e_year), int(e_copies)
                        if safe_commit(db):
                            st.success("Book updated.")
                            st.rerun()
                if st.button("Delete selected book", type="secondary"):
                    history = db.scalar(select(func.count(Loan.id)).where(Loan.book_id == chosen.id)) or 0
                    if history:
                        st.error("This book has loan history and cannot be deleted. Set its total copies as needed instead.")
                    else:
                        db.delete(chosen)
                        if safe_commit(db):
                            st.success("Book deleted.")
                            st.rerun()
        else:
            st.info("Book changes are available to administrators.")

    # -------------------- Issue / Return --------------------
    elif page == "Issue / Return":
        st.title("🔄 Issue & Return")
        st.caption("Manage circulation and overdue fines.")
        with st.form("issue_form"):
            st.subheader("Issue a book")
            active_books = db.scalars(select(Book).order_by(Book.title)).all()
            active_members = db.scalars(select(Member).where(Member.active == 1).order_by(Member.name)).all()
            book_options = [b for b in active_books if available_copies(db, b.id) > 0]
            if not book_options:
                st.warning("No books are currently available to issue.")
            if not active_members:
                st.warning("Add an active member before issuing books.")
            chosen_book = st.selectbox("Book", book_options, format_func=lambda b: f"{b.title} ({available_copies(db, b.id)} available)") if book_options else None
            chosen_member = st.selectbox("Member", active_members, format_func=lambda m: f"{m.name} — {m.member_code}") if active_members else None
            due_date = st.date_input("Due date", value=date.today() + timedelta(days=LOAN_DAYS), min_value=date.today())
            notes = st.text_input("Notes (optional)")
            issue = st.form_submit_button("Issue book", type="primary", disabled=not (book_options and active_members))
        if issue and chosen_book and chosen_member:
            duplicate = db.scalar(select(Loan.id).where(Loan.book_id == chosen_book.id,
                Loan.member_id == chosen_member.id, Loan.returned_on.is_(None)))
            if duplicate:
                st.error("This member already has an active loan for this book.")
            elif available_copies(db, chosen_book.id) < 1:
                st.error("No copies remain available. Refresh and try again.")
            else:
                db.add(Loan(book_id=chosen_book.id, member_id=chosen_member.id,
                            issued_on=date.today(), due_on=due_date, notes=notes.strip()))
                if safe_commit(db):
                    st.success(f"Issued '{chosen_book.title}' to {chosen_member.name}.")
                    st.rerun()
        st.divider()
        st.subheader("Active loans")
        active_loans = db.scalars(select(Loan).where(Loan.returned_on.is_(None)).order_by(Loan.due_on)).all()
        if active_loans:
            active_rows = [{"Loan ID": l.id, "Book": l.book.title, "Member": l.member.name,
                            "Member code": l.member.member_code, "Issued": l.issued_on,
                            "Due": l.due_on, "Days overdue": max(0, (date.today()-l.due_on).days),
                            "Estimated fine": money(current_fine(l.due_on))} for l in active_loans]
            st.dataframe(pd.DataFrame(active_rows), use_container_width=True, hide_index=True)
            choices = {f"#{l.id} · {l.book.title} — {l.member.name} (due {l.due_on})": l.id for l in active_loans}
            selected_label = st.selectbox("Select loan to return", list(choices.keys()))
            selected_loan = db.get(Loan, choices[selected_label])
            fine = current_fine(selected_loan.due_on)
            st.write(f"Estimated fine: **{money(fine)}**")
            if st.button("Confirm return", type="primary"):
                selected_loan.returned_on = date.today()
                selected_loan.fine_paid = fine
                if safe_commit(db):
                    st.success(f"Return recorded. Fine due: {money(fine)}.")
                    st.rerun()
        else:
            st.info("There are no active loans.")
        with st.expander("View loan history"):
            history = db.scalars(select(Loan).order_by(Loan.id.desc()).limit(100)).all()
            hist_rows = [{"Loan ID": l.id, "Book": l.book.title, "Member": l.member.name,
                          "Issued": l.issued_on, "Due": l.due_on, "Returned": l.returned_on or "Not returned",
                          "Fine": money(l.fine_paid if l.returned_on else current_fine(l.due_on))}
                         for l in history]
            if hist_rows:
                st.dataframe(pd.DataFrame(hist_rows), use_container_width=True, hide_index=True)
            else:
                st.info("Loan history will appear here.")

    # -------------------- Members --------------------
    elif page == "Members":
        st.title("👥 Members")
        st.caption("Maintain member details and membership status.")
        member_search = st.text_input("Search members by name, code, email or department")
        member_query = select(Member).order_by(Member.name)
        if member_search.strip():
            p = f"%{member_search.strip()}%"
            member_query = member_query.where(or_(Member.name.ilike(p), Member.member_code.ilike(p),
                                                  Member.email.ilike(p), Member.department.ilike(p)))
        members_list = db.scalars(member_query).all()
        member_rows = [{"ID": m.id, "Member code": m.member_code, "Name": m.name, "Email": m.email,
                        "Phone": m.phone, "Department": m.department, "Joined": m.joined_on,
                        "Status": "Active" if m.active else "Inactive"} for m in members_list]
        if member_rows:
            st.dataframe(pd.DataFrame(member_rows), use_container_width=True, hide_index=True)
            csv_download(pd.DataFrame(member_rows), "library_members.csv", "⬇ Export members CSV")
        if st.session_state.user_role == "admin":
            st.divider()
            st.subheader("Register a member")
            with st.form("add_member_form", clear_on_submit=True):
                mc1, mc2 = st.columns(2)
                code = mc1.text_input("Member code *", placeholder="MEM004")
                name = mc2.text_input("Full name *")
                email = mc1.text_input("Email *")
                phone = mc2.text_input("Phone")
                department = st.text_input("Department / course")
                joined = st.date_input("Joining date", value=date.today())
                add_member = st.form_submit_button("Register member", type="primary")
            if add_member:
                if not code.strip() or not name.strip() or not email.strip():
                    st.error("Member code, name and email are required.")
                elif db.scalar(select(Member.id).where(or_(Member.member_code == code.strip(), func.lower(Member.email) == email.strip().lower()))):
                    st.error("Member code or email already exists.")
                else:
                    db.add(Member(member_code=code.strip().upper(), name=name.strip(),
                                  email=email.strip().lower(), phone=phone.strip(),
                                  department=department.strip(), joined_on=joined))
                    if safe_commit(db):
                        st.success("Member registered.")
                        st.rerun()
            if members_list:
                st.subheader("Update member status")
                target = st.selectbox("Choose member", members_list, format_func=lambda m: f"{m.name} — {m.member_code}", key="member_edit")
                new_status = st.selectbox("Status", ["Active", "Inactive"], index=0 if target.active else 1)
                if st.button("Save member status"):
                    target.active = 1 if new_status == "Active" else 0
                    if safe_commit(db):
                        st.success("Member status updated.")
                        st.rerun()
        else:
            st.info("Only administrators can register members or update their status.")

    # -------------------- Reports --------------------
    elif page == "Reports":
        st.title("📊 Reports & Analytics")
        all_books = db.scalars(select(Book)).all()
        all_loans = db.scalars(select(Loan).order_by(Loan.issued_on.desc())).all()
        all_members = db.scalars(select(Member)).all()
        loan_rows = []
        for l in all_loans:
            loan_rows.append({
                "Loan ID": l.id, "ISBN": l.book.isbn, "Book": l.book.title,
                "Member code": l.member.member_code, "Member": l.member.name,
                "Issued on": l.issued_on, "Due on": l.due_on,
                "Returned on": l.returned_on or "",
                "Status": "Returned" if l.returned_on else ("Overdue" if l.due_on < date.today() else "On loan"),
                "Fine (INR)": l.fine_paid if l.returned_on else current_fine(l.due_on)
            })
        loans_df = pd.DataFrame(loan_rows)
        r1, r2, r3 = st.columns(3)
        r1.metric("Total transactions", len(all_loans))
        r2.metric("Fines recorded", money(sum(l.fine_paid for l in all_loans)))
        r3.metric("Currently overdue", sum(1 for l in all_loans if not l.returned_on and l.due_on < date.today()))
        if not loans_df.empty:
            st.subheader("Borrowing status")
            st.bar_chart(loans_df["Status"].value_counts())
            st.subheader("Most borrowed books")
            st.bar_chart(loans_df["Book"].value_counts().head(10))
            st.subheader("Loan records")
            st.dataframe(loans_df, use_container_width=True, hide_index=True)
            csv_download(loans_df, "library_loan_report.csv", "⬇ Download loan report")
        else:
            st.info("Reports will appear after books are issued.")
        st.subheader("Availability report")
        stock_rows = [{"ISBN": b.isbn, "Title": b.title, "Author": b.author,
                       "Total": b.total_copies, "Available": available_copies(db, b.id),
                       "On loan": b.total_copies - available_copies(db, b.id)} for b in all_books]
        stock_df = pd.DataFrame(stock_rows)
        if not stock_df.empty:
            st.dataframe(stock_df, use_container_width=True, hide_index=True)
            csv_download(stock_df, "library_stock_report.csv", "⬇ Download stock report")

    # -------------------- User accounts --------------------
    elif page == "User Accounts":
        st.title("🔐 User Accounts")
        st.caption("Create member logins or disable access. Only administrators can access this page.")
        users = db.scalars(select(User).order_by(User.id)).all()
        st.dataframe(pd.DataFrame([{"ID": u.id, "Name": u.name, "Email": u.email,
                                    "Role": u.role.title(), "Status": "Active" if u.active else "Inactive"}
                                   for u in users]), use_container_width=True, hide_index=True)
        st.subheader("Create login")
        with st.form("create_user_form", clear_on_submit=True):
            u_name = st.text_input("Name")
            u_email = st.text_input("Email")
            u_password = st.text_input("Temporary password (minimum 10 characters)", type="password")
            u_role = st.selectbox("Role", ["member", "admin"])
            create_user = st.form_submit_button("Create account", type="primary")
        if create_user:
            if not u_name.strip() or not u_email.strip() or len(u_password) < 10:
                st.error("Enter a name, email and password of at least 10 characters.")
            elif db.scalar(select(User.id).where(func.lower(User.email) == u_email.strip().lower())):
                st.error("An account with this email already exists.")
            else:
                db.add(User(name=u_name.strip(), email=u_email.strip().lower(),
                            password_hash=hash_password(u_password), role=u_role))
                if safe_commit(db):
                    st.success("Account created.")
                    st.rerun()
        st.subheader("Activate / deactivate account")
        candidates = [u for u in users if u.id != st.session_state.user_id]
        if candidates:
            selected_user = st.selectbox("Choose account", candidates, format_func=lambda u: f"{u.name} — {u.email}")
            status = st.selectbox("Account status", ["Active", "Inactive"], index=0 if selected_user.active else 1)
            if st.button("Update account status"):
                selected_user.active = 1 if status == "Active" else 0
                if safe_commit(db):
                    st.success("Account status updated.")
                    st.rerun()

    # -------------------- Settings --------------------
    elif page == "Settings":
        st.title("⚙️ Settings & Project Information")
        st.write("Configure borrowing rules using deployment environment variables.")
        st.code(f"LOAN_DAYS={LOAN_DAYS}\nFINE_PER_DAY={FINE_PER_DAY}")
        st.markdown("""
**Current features**
- Role-based login (administrator and member account roles)
- Password hashing using PBKDF2
- Book catalog CRUD and availability tracking
- Member registration and activation/deactivation
- Issue/return workflow and overdue fine calculation
- Dashboard metrics, charts, CSV exports
- SQLite for local development; PostgreSQL support for hosted persistence

**Important notes**
- This is a student project starter, not a certified production library platform.
- The current member role can view catalog, circulation, members, and reports. If you deploy for real users, restrict member access to their own records and add password reset, rate limiting, backups, and stronger operational controls.
- Configure `DATABASE_URL`, `ADMIN_EMAIL`, and `ADMIN_PASSWORD` in your hosting provider's secrets/settings. Never commit secrets to GitHub.
- Fines are calculated for demonstration purposes; the app does not process online payments.
""")
        st.markdown("Deployment guide: [Streamlit Community Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy) · Database option: [Supabase](https://supabase.com/)")

st.caption("LibraDesk · BCS Final-Year Project · Built with Python, Streamlit and SQLAlchemy")
