# LibraDesk — Library Management System

A BCS final-year project starter built with Python, Streamlit, SQLAlchemy and SQLite/PostgreSQL.

## Features

- Admin login and user-account management
- Password hashing (PBKDF2-HMAC-SHA256)
- Book catalog: add, edit, delete (where no loan history exists), search and availability
- Member registration and active/inactive status
- Book issue and return workflow
- Due dates and configurable overdue fines
- Dashboard metrics, category/borrowing charts and CSV exports
- SQLite for local development; PostgreSQL through `DATABASE_URL` for hosted persistence
- Demo seed records for books and members

## Run locally on Windows

Use Python 3.12 or 3.13 for the smoothest compatibility with hosted Python environments.

1. Extract this ZIP.
2. Open Command Prompt in the extracted `bcs_library_management_system` folder.
3. Create and activate a virtual environment:

   ```bat
   py -3.12 -m venv .venv
   .venv\Scripts\activate
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   streamlit run app.py
   ```

4. Open the local URL printed by Streamlit, normally `http://localhost:8501`.

### First-run demo administrator

- Email: `admin@library.local`
- Password: `ChangeMe123!`

Change these before publishing publicly. The app creates this account only if the configured admin email does not already exist.

To customize the first admin account before the first run, set environment variables in Command Prompt:

```bat
set ADMIN_EMAIL=your-admin@example.com
set ADMIN_PASSWORD=YourLongUniquePassword123!
streamlit run app.py
```

If the database has already been initialized, changing these environment variables does not change the existing account's password.

## Free hosting with persistent data

Recommended setup: **Streamlit Community Cloud + Supabase PostgreSQL**.

### A. Create the database

1. Create a free project at https://supabase.com/.
2. In the Supabase project, open **Connect** or the database connection settings.
3. Copy a PostgreSQL connection URI. Prefer the provider-recommended connection method for your hosting environment; use a pooler URI if Supabase recommends it for your network.
4. Keep the database password private. If the URI contains a placeholder, replace it with your actual database password.
5. The app creates its tables automatically on first start.

### B. Upload to GitHub

1. Create a new GitHub repository, for example `bcs-library-management`.
2. Upload `app.py`, `requirements.txt`, `.gitignore`, `.streamlit/config.toml`, and `README.md`.
3. Do not upload `library.db`, `.env`, or `.streamlit/secrets.toml`.
4. Do not put database credentials in source code or a public repository.

### C. Deploy the app

1. Visit https://share.streamlit.io/ and sign in with GitHub.
2. Choose **Create app**.
3. Select your repository, branch `main`, and entrypoint `app.py`.
4. Open **Advanced settings** / **Secrets** and add:

   ```toml
   DATABASE_URL = "postgresql+psycopg://postgres.YOUR_PROJECT:YOUR_DATABASE_PASSWORD@YOUR_DATABASE_HOST:5432/postgres"
   ADMIN_EMAIL = "your-admin@example.com"
   ADMIN_PASSWORD = "Use-A-Long-Unique-Password!"
   FINE_PER_DAY = "5"
   LOAN_DAYS = "14"
   ```

   Replace the example database URI with the exact connection URI supplied by your database provider. Do not copy the sample placeholder literally. If the provider gives a `postgres://` or `postgresql://` URI, the app normalizes it automatically.

5. Select Python 3.12 if prompted, then deploy.
6. Wait for the build to finish and open the public `streamlit.app` URL.
7. Sign in with the configured admin email/password.

### Free-tier and persistence notes

- Streamlit Community Cloud is free for eligible apps, but apps may sleep and have resource limits.
- Use PostgreSQL for hosted data. The local SQLite file is suitable for development but should not be relied on for persistent storage on an ephemeral hosted filesystem.
- Supabase free-plan limits and policies can change; check the current plan details and keep backups of important project data.
- Never use real student records or confidential personal information in a public demonstration app.
- Anyone with admin credentials can modify the library. Keep admin credentials private.

## Project structure

```text
bcs_library_management_system/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
└── .streamlit/
    └── config.toml
```

## Main database tables

- `users`: account identity, role, active status, password hash
- `books`: ISBN, title, author, category, publisher, year, copies
- `members`: member code, name, email, phone, department, status
- `loans`: book, member, issue date, due date, return date, fine

## Suggested viva explanation

**Problem:** Manual library records make it difficult to track availability, due dates, member records and overdue books.

**Solution:** A web-based library management application with centralized catalog and member records, controlled circulation, automated overdue-fine calculation and downloadable reports.

**Future enhancements:** Member self-service pages, email reminders, barcode/QR scanning, PDF receipts, password reset, audit logs, backups and finer-grained role permissions.
