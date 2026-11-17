
import sqlite3
import re
from datetime import datetime, date, timedelta


# ==========================================================
# DOSEMATE - MEDICATION SCHEDULING AND ADHERENCE TRACKER
# ==========================================================

DB_NAME = "dosemate.db"

conn = sqlite3.connect(DB_NAME)
conn.execute("PRAGMA foreign_keys = ON")
cursor = conn.cursor()


# ==========================================================
# 1. DATABASE SETUP
# ==========================================================

def create_tables():
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS medicines (
            medicine_id INTEGER PRIMARY KEY AUTOINCREMENT,
            medicine_name TEXT NOT NULL,
            dosage TEXT NOT NULL,
            tablets_available INTEGER NOT NULL,
            timings TEXT NOT NULL,
            duration_days INTEGER NOT NULL,
            start_date TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dose_records (
            dose_id INTEGER PRIMARY KEY AUTOINCREMENT,
            medicine_id INTEGER NOT NULL,
            dose_date TEXT NOT NULL,
            scheduled_time TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            FOREIGN KEY (medicine_id)
                REFERENCES medicines(medicine_id),
            UNIQUE (medicine_id, dose_date, scheduled_time)
        )
    """)

    conn.commit()


# ==========================================================
# 2. INPUT VALIDATION FUNCTIONS
# ==========================================================

def get_positive_integer(message):
    while True:
        try:
            value = int(input(message))

            if value <= 0:
                print("Please enter a number greater than zero.")
                continue

            return value

        except ValueError:
            print("Invalid input. Please enter a whole number.")


def get_stock():
    while True:
        try:
            stock = float(input("Enter available tablets: "))

            if stock < 0:
                print("Stock cannot be negative.")
                continue

            return stock

        except ValueError:
            print("Invalid stock. Please enter a number.")


def get_dosage():
    while True:
        dosage = input(
            "Enter dosage (example: 1 tablet or 0.5 tablet): "
        ).strip().lower()

        match = re.fullmatch(
            r"(\d+(?:\.\d+)?)\s+tablets?",
            dosage
        )

        if match:
            amount = float(match.group(1))

            if amount > 0:
                return dosage, amount

        print("Invalid dosage. Example: 1 tablet or 0.5 tablet.")


def get_timings():
    while True:
        raw_timings = input(
            "Enter medicine times separated by commas "
            "(example: 08:00,14:00,20:00): "
        ).strip()

        try:
            times = []

            for item in raw_timings.split(","):
                item = item.strip()

                parsed_time = datetime.strptime(item, "%H:%M")
                normalized_time = parsed_time.strftime("%H:%M")

                if normalized_time not in times:
                    times.append(normalized_time)

            if times:
                return sorted(times)

        except ValueError:
            pass

        print("Invalid time. Use the 24-hour format HH:MM.")
        print("Example: 08:00,14:00,20:00")


def get_start_date():
    while True:
        raw_date = input(
            "Enter start date (YYYY-MM-DD) "
            "or press Enter for today: "
        ).strip()

        if raw_date == "":
            return date.today().isoformat()

        try:
            parsed_date = datetime.strptime(
                raw_date, "%Y-%m-%d"
            ).date()

            return parsed_date.isoformat()

        except ValueError:
            print("Invalid date. Example: 2026-11-17.")


# ==========================================================
# 3. ADD MEDICINE
# ==========================================================

def add_medicine():
    print("\n========== ADD MEDICINE ==========")

    while True:
        name = input("Enter medicine name: ").strip()

        if name:
            break

        print("Medicine name cannot be empty.")

    dosage, dosage_amount = get_dosage()
    stock = get_stock()
    duration = get_positive_integer("Enter duration in days: ")
    timings = get_timings()
    start_date = get_start_date()

    try:
        cursor.execute("""
            INSERT INTO medicines (
                medicine_name,
                dosage,
                tablets_available,
                timings,
                duration_days,
                start_date
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            name,
            dosage,
            stock,
            ",".join(timings),
            duration,
            start_date
        ))

        conn.commit()

        print("\nMedicine added successfully!")
        print("Medicine ID:", cursor.lastrowid)

    except sqlite3.Error as error:
        conn.rollback()
        print("Database error:", error)


# ==========================================================
# 4. VIEW ALL MEDICINES
# ==========================================================

def view_medicines():
    print("\n========== MEDICINE DETAILS ==========")

    cursor.execute("""
        SELECT * FROM medicines
        ORDER BY medicine_id
    """)

    medicines = cursor.fetchall()

    if not medicines:
        print("No medicines have been added yet.")
        return

    for medicine in medicines:
        print("--------------------------------------")
        print("Medicine ID :", medicine[0])
        print("Name        :", medicine[1])
        print("Dosage      :", medicine[2])
        print("Stock       :", medicine[3], "tablets")
        print("Timings     :", medicine[4])
        print("Duration    :", medicine[5], "days")
        print("Start Date  :", medicine[6])

    print("--------------------------------------")


# ==========================================================
# 5. CHECK WHETHER MEDICINE IS ACTIVE TODAY
# ==========================================================

def is_active_today(start_date, duration):
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    today = date.today()

    end = start + timedelta(days=duration - 1)

    return start <= today <= end


# ==========================================================
# 6. CREATE TODAY'S DOSE RECORDS
# ==========================================================

def ensure_today_records():
    today = date.today().isoformat()

    cursor.execute("""
        SELECT medicine_id, timings, start_date, duration_days
        FROM medicines
    """)

    medicines = cursor.fetchall()

    for medicine in medicines:
        medicine_id, timings, start_date, duration = medicine

        if not is_active_today(start_date, duration):
            continue

        for scheduled_time in timings.split(","):
            cursor.execute("""
                INSERT OR IGNORE INTO dose_records (
                    medicine_id,
                    dose_date,
                    scheduled_time,
                    status
                )
                VALUES (?, ?, ?, 'Pending')
            """, (
                medicine_id,
                today,
                scheduled_time
            ))

    conn.commit()


# ==========================================================
# 7. GENERATE TODAY'S SCHEDULE
# ==========================================================

def generate_schedule():
    print("\n========== TODAY'S MEDICINE SCHEDULE ==========")

    ensure_today_records()

    today = date.today().isoformat()

    cursor.execute("""
        SELECT
            dose_records.dose_id,
            medicines.medicine_name,
            medicines.dosage,
            dose_records.scheduled_time,
            dose_records.status
        FROM dose_records
        JOIN medicines
            ON dose_records.medicine_id = medicines.medicine_id
        WHERE dose_records.dose_date = ?
        ORDER BY dose_records.scheduled_time
    """, (today,))

    records = cursor.fetchall()

    if not records:
        print("No medicines are scheduled for today.")
        return

    for record in records:
        dose_id, name, dosage, timing, status = record

        display_time = datetime.strptime(
            timing, "%H:%M"
        ).strftime("%I:%M %p")

        print("--------------------------------------")
        print("Dose ID  :", dose_id)
        print("Time     :", display_time)
        print("Medicine :", name)
        print("Dosage   :", dosage)
        print("Status   :", status)

    print("--------------------------------------")


# ==========================================================
# 8. MARK DOSE AS TAKEN OR MISSED
# ==========================================================

def mark_dose():
    print("\n========== MARK DOSE ==========")

    ensure_today_records()

    today = date.today().isoformat()

    cursor.execute("""
        SELECT
            dose_records.dose_id,
            medicines.medicine_name,
            medicines.dosage,
            dose_records.scheduled_time,
            dose_records.status
        FROM dose_records
        JOIN medicines
            ON dose_records.medicine_id = medicines.medicine_id
        WHERE dose_records.dose_date = ?
        ORDER BY dose_records.scheduled_time
    """, (today,))

    records = cursor.fetchall()

    if not records:
        print("No doses are scheduled for today.")
        return

    print("\nToday's doses:")

    for record in records:
        print(
            "Dose ID:", record[0],
            "| Medicine:", record[1],
            "| Time:", record[3],
            "| Status:", record[4]
        )

    try:
        dose_id = int(input("\nEnter Dose ID: "))

    except ValueError:
        print("Invalid Dose ID. Enter a number.")
        return

    cursor.execute("""
        SELECT
            dose_records.status,
            dose_records.medicine_id,
            medicines.dosage,
            medicines.tablets_available,
            medicines.medicine_name
        FROM dose_records
        JOIN medicines
            ON dose_records.medicine_id = medicines.medicine_id
        WHERE dose_records.dose_id = ?
          AND dose_records.dose_date = ?
    """, (dose_id, today))

    record = cursor.fetchone()

    if record is None:
        print("Dose ID not found.")
        return

    status, medicine_id, dosage, stock, medicine_name = record

    if status != "Pending":
        print("This dose has already been marked as", status)
        return

    print("\n1. Taken")
    print("2. Missed")

    choice = input("Choose an option: ").strip()

    if choice not in ("1", "2"):
        print("Invalid choice. Enter 1 or 2.")
        return

    new_status = "Taken" if choice == "1" else "Missed"

    # Reduce stock only when the medicine is taken.
    if new_status == "Taken":
        match = re.fullmatch(
            r"(\d+(?:\.\d+)?)\s+tablets?",
            dosage.strip().lower()
        )

        if not match:
            print("Cannot calculate stock. Please check the dosage.")
            return

        amount = float(match.group(1))
        current_stock = float(stock)

        if current_stock < amount:
            print("Not enough tablets in stock.")
            print("Dose was not marked as Taken.")
            return

        new_stock = current_stock - amount

        try:
            cursor.execute("""
                UPDATE medicines
                SET tablets_available = ?
                WHERE medicine_id = ?
            """, (new_stock, medicine_id))

        except sqlite3.Error as error:
            conn.rollback()
            print("Could not update stock:", error)
            return

    try:
        cursor.execute("""
            UPDATE dose_records
            SET status = ?
            WHERE dose_id = ?
              AND dose_date = ?
              AND status = 'Pending'
        """, (new_status, dose_id, today))

        if cursor.rowcount == 0:
            conn.rollback()
            print("Dose could not be updated.")
            return

        conn.commit()
        print("Dose successfully marked as", new_status)

        if new_status == "Taken":
            print("Medicine stock has been updated.")

    except sqlite3.Error as error:
        conn.rollback()
        print("Database error:", error)


# ==========================================================
# 9. MEDICINE-WISE ADHERENCE REPORT
# ==========================================================

def adherence_report():
    print("\n========== ADHERENCE REPORT ==========")

    cursor.execute("""
        SELECT medicine_id, medicine_name
        FROM medicines
        ORDER BY medicine_name
    """)

    medicines = cursor.fetchall()

    if not medicines:
        print("No medicines available.")
        return

    for medicine_id, medicine_name in medicines:

        cursor.execute("""
            SELECT
                SUM(CASE WHEN status = 'Taken' THEN 1 ELSE 0 END),
                SUM(CASE WHEN status = 'Missed' THEN 1 ELSE 0 END)
            FROM dose_records
            WHERE medicine_id = ?
        """, (medicine_id,))

        result = cursor.fetchone()

        taken = result[0] or 0
        missed = result[1] or 0

        completed = taken + missed

        if completed == 0:
            percentage = 0
        else:
            percentage = (taken / completed) * 100

        print("--------------------------------------")
        print("Medicine          :", medicine_name)
        print("Doses Taken       :", taken)
        print("Doses Missed      :", missed)
        print("Completed Doses   :", completed)
        print("Adherence         :", round(percentage, 2), "%")

    print("--------------------------------------")


# ==========================================================
# 10. LOW STOCK ALERT
# ==========================================================

def stock_alert():
    print("\n========== TABLET STOCK ALERT ==========")

    cursor.execute("""
        SELECT
            medicine_name,
            dosage,
            tablets_available,
            timings,
            start_date,
            duration_days
        FROM medicines
    """)

    medicines = cursor.fetchall()

    if not medicines:
        print("No medicines available.")
        return

    alert_found = False
    today = date.today()

    for medicine in medicines:
        name, dosage, stock, timings, start_date, duration = medicine

        if not is_active_today(start_date, duration):
            continue

        match = re.fullmatch(
            r"(\d+(?:\.\d+)?)\s+tablets?",
            dosage.strip().lower()
        )

        if not match:
            print("Cannot calculate stock for", name)
            continue

        amount_per_dose = float(match.group(1))
        doses_per_day = len(timings.split(","))

        daily_usage = amount_per_dose * doses_per_day

        if daily_usage <= 0:
            continue

        remaining_days = float(stock) / daily_usage

        print("--------------------------------------")
        print("Medicine       :", name)
        print("Available      :", stock, "tablets")
        print("Daily Usage    :", daily_usage, "tablets")

        print(
            "Stock will last approximately:",
            round(remaining_days, 2),
            "days"
        )

        if remaining_days < 3:
            alert_found = True
            print("WARNING: LOW STOCK! Refill is needed soon.")

    if not alert_found:
        print("\nNo low-stock alerts at the moment.")

    print("--------------------------------------")


# ==========================================================
# 11. WEEKLY CAREGIVER REPORT
# ==========================================================

def weekly_report():
    print("\n========== WEEKLY CAREGIVER REPORT ==========")

    today = date.today()
    week_start = today - timedelta(days=6)

    cursor.execute("""
        SELECT
            medicines.medicine_name,
            SUM(CASE WHEN dose_records.status = 'Taken'
                     THEN 1 ELSE 0 END),
            SUM(CASE WHEN dose_records.status = 'Missed'
                     THEN 1 ELSE 0 END)
        FROM dose_records
        JOIN medicines
            ON dose_records.medicine_id = medicines.medicine_id
        WHERE dose_records.dose_date BETWEEN ? AND ?
        GROUP BY medicines.medicine_id, medicines.medicine_name
        ORDER BY medicines.medicine_name
    """, (
        week_start.isoformat(),
        today.isoformat()
    ))

    records = cursor.fetchall()

    if not records:
        print("No dose records found for the last 7 days.")
        return

    print(
        "Period:",
        week_start.strftime("%d-%m-%Y"),
        "to",
        today.strftime("%d-%m-%Y")
    )

    for name, taken, missed in records:
        taken = taken or 0
        missed = missed or 0
        total = taken + missed

        percentage = (taken / total * 100) if total else 0

        print("--------------------------------------")
        print("Medicine       :", name)
        print("Taken          :", taken)
        print("Missed         :", missed)
        print("Adherence      :", round(percentage, 2), "%")

    print("--------------------------------------")


# ==========================================================
# 12. MAIN MENU
# ==========================================================

def main():
    create_tables()

    while True:
        print("\n")
        print("==========================================")
        print("       DOSEMATE - MEDICATION TRACKER")
        print("==========================================")
        print("1. Add Medicine")
        print("2. View All Medicines")
        print("3. Generate Today's Schedule")
        print("4. Mark Dose as Taken / Missed")
        print("5. View Adherence Report")
        print("6. Check Tablet Stock Alert")
        print("7. Weekly Caregiver Report")
        print("8. Exit")
        print("==========================================")

        choice = input("Enter your choice (1-8): ").strip()

        if choice == "1":
            add_medicine()

        elif choice == "2":
            view_medicines()

        elif choice == "3":
            generate_schedule()

        elif choice == "4":
            mark_dose()

        elif choice == "5":
            adherence_report()

        elif choice == "6":
            stock_alert()

        elif choice == "7":
            weekly_report()

        elif choice == "8":
            print("\nThank you for using DoseMate!")
            break

        else:
            print("Invalid menu choice. Please enter a number from 1 to 8.")


# ==========================================================
# 13. PROGRAM STARTING POINT
# ==========================================================

if __name__ == "__main__":
    try:
        main()

    except KeyboardInterrupt:
        print("\nProgram stopped.")

    except sqlite3.Error as error:
        print("\nDatabase error:", error)

    finally:
        conn.close()
