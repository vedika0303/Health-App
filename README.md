 Desktop health management application built with Python's Tkinter GUI framework and MySQL. It helps users track vaccination schedules, manage tablet/medication reminders, look up common disease info, and stay on top of health notifications — all through a clean pastel-themed interface.

Features


User Accounts – create an account and log in with a phone number, password, and date of birth
Vaccine Tracker – view a checklist of vaccines (with per-dose tracking), mark doses as completed, and see a summary of remaining vs. completed doses
View Vaccines – browse a reference table of common vaccines with age eligibility, number of doses, gap between doses, and what each vaccine protects against
Tablet Tracker – add medications with custom schedules:

One-time, daily, twice-a-day, or custom duration (start–end date) reminders
Multiple times per day (comma-separated)
Attach a prescription image for reference



Common Diseases Reference – quick lookup of common ailments (cold, fever, headache, stomach pain) with suggested medication and guidance on when to see a doctor, with the option to set a reminder to monitor symptoms
Notification Box – view all pending reminders (vaccines, tablets, disease monitoring), search/filter them, and mark them as taken individually or in bulk
Automatic DB Schema Migration – the app checks and updates its own database schema on startup (e.g., adding a dose column if missing)


Tech Stack


Language: Python
GUI: Tkinter (with ttk widgets)
Database: MySQL (via mysql-connector-python)


Requirements

mysql-connector-python

Tkinter comes bundled with most standard Python installations. Install the database connector with:

bashpip install mysql-connector-python

You'll also need MySQL Server installed and running locally.

Setup & Installation


Clone this repository:


bash   git clone https://github.com/YOUR-USERNAME/health-app.git
   cd health-app


Install the required package (see above).
Set up your MySQL connection. Open the source file and update the DB_CONFIG dictionary with your own credentials:


python   DB_CONFIG = {
       "host": "localhost",
       "user": "root",
       "password": "your_password_here",
       "database": "health_app"
   }


Run the program:


bash   python Health_App.py

On first run, the app automatically creates the health_app database and its required tables (users, reminders, vaccines_taken).

How to Use


Click Create Account to register with a phone number, password, and date of birth.
Click Logout / Login to log in with your credentials.
Use the main menu buttons to:

Vaccine Tracker – check off vaccine doses you've received
Tablet Tracker – add medications, set schedules, and optionally attach a prescription photo
View Vaccines – look up vaccine details in a reference table
Common Diseases – check suggested medication for common ailments and set a monitoring reminder
Notification Box – review, search, and mark reminders as taken (individually or in bulk)





Database Schema

users

ColumnTypeusername (phone)VARCHAR(50), Primary KeypasswordVARCHAR(255)dobDATE

reminders

ColumnTypeidINT, Auto Increment, Primary KeyusernameVARCHAR(50)typeVARCHAR(20) — vaccine / tablet / diseaseitemVARCHAR(200)timeDATETIMEinfoTEXT

vaccines_taken

ColumnTypeusernameVARCHAR(50)vaccineVARCHAR(100)doseINT
