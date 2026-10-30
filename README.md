# Church Register

A Django app for registering church members and visitors and taking attendance at services.

## Features
- **Members:** name, gender, date of birth, phone, email, address, cell, ministry, member-since date, status, notes
- **Visitors:** first-time guests with follow-up status (Pending / Contacted / Joined), plus a "Make member" button
- **Check-in:** open a service (date + type), search people and tap **Check in**. Several ushers can check people in at once. Add first-time visitors on the spot and enter an extra headcount for people not recorded by name.
- **Dashboard:** member count, last service, average attendance, new visitors, pending follow-ups, a 12-service chart and this month's birthdays
- **Reports:** attendance by date range, each member's attendance rate, members who missed 3+ services in a row, and CSV exports
- **Admin** at `/admin/` for ministries, service types, user accounts and raw data

## First-time setup
```bash
cd ~/Documents/Church
source venv/bin/activate
python manage.py migrate
python manage.py createsuperuser   # your own login
```

## Run it
```bash
source venv/bin/activate
python manage.py runserver
```
Then open http://127.0.0.1:8000 and sign in.

To let ushers on the church Wi-Fi use their phones, run
`python manage.py runserver 0.0.0.0:8000`, add this computer's IP address to `ALLOWED_HOSTS` in `config/settings.py`,
and have them open `http://<this-computer's-IP>:8000`.

## Adding ushers
Go to **Admin → Users → Add user** and create a username and password for each usher. They don't need "staff status" unless they should see the admin site.

## Settings
- Church name: set the `CHURCH_NAME` environment variable, e.g. `CHURCH_NAME="Grace Community Church" python manage.py runserver`
  (or change the default in `config/settings.py`).
- Time zone: set `TIME_ZONE` (e.g. `Africa/Nairobi`) so "today" matches your local date.
- Service types and ministries: edit them in the admin.

## Tests
```bash
python manage.py test registry
```

## Before hosting it on the internet
Set the `DJANGO_SECRET_KEY` environment variable to a long random value (e.g. from `python -c "import secrets; print(secrets.token_urlsafe(50))"`), set `DEBUG = False`, fill in `ALLOWED_HOSTS`, and run `python manage.py collectstatic`.
Back up `db.sqlite3` regularly: it holds all your records.

## Project layout
- `config/`: Django settings and root URLs
- `registry/models.py`: Member, Visitor, Service, Attendance, Ministry, ServiceType
- `registry/views.py`: pages and CSV exports
- `registry/stats.py`: attendance calculations (rates, absence streaks, chart)
- `registry/templates/registry/`: HTML pages
- `registry/static/registry/style.css`: styling (supports light and dark mode)
