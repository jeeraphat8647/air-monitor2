from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import csv
import os
import re
import datetime
import subprocess

# ================= CONFIG =================

URL = "http://182.52.103.224/"

# ===== USE CURRENT DIRECTORY (GitHub Actions) =====
BASE_DIR = os.getcwd()

DATA_DIR = os.path.join(BASE_DIR, "data")
LOG_DIR = os.path.join(BASE_DIR, "log")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

CSV_PATH = os.path.join(DATA_DIR, "air_data.csv")
LOG_PATH = os.path.join(LOG_DIR, "air_log.txt")

# ================= LOG =================
def write_log(msg):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{now}] {msg}"
    print(line)

    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")

# ================= LOAD SAVED RECORDS =================
def get_saved_records():
    records = set()

    if not os.path.exists(CSV_PATH):
        return records

    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader, None)

        for row in reader:
            key = f"{row[0]}_{row[1]}_{row[2]}"
            records.add(key)

    return records

# ================= EXTRACT DATA =================
def get_data(driver):
    popup = WebDriverWait(driver,10).until(
        EC.presence_of_element_located(
            (By.CLASS_NAME,"leaflet-popup-content"))
    )

    text = popup.text
    station = text.split("\n")[0]

    # ===== DATE TIME =====
    datetime_match = re.search(
        r"อัพเดทข้อมูลเวลา\s*(.+?\d{2}:\d{2})", text
    )

    date = ""
    time_data = ""

    if datetime_match:
        dt_text = datetime_match.group(1)
        parts = dt_text.rsplit(" ",1)

        date = parts[0]
        time_data = parts[1]
    else:
        write_log("⚠️ Date parse failed")

    benzene_match = re.search(r"เบนซีน\s*([\d\.]+)", text)
    butadiene_match = re.search(r"1,3-บิวทาไดอีน\s*([\d\.]+)", text)

    benzene = float(benzene_match.group(1)) if benzene_match else None
    butadiene = float(butadiene_match.group(1)) if butadiene_match else None

    return station, date, time_data, benzene, butadiene

# ================= DRIVER =================
def create_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--log-level=3")

    driver = webdriver.Chrome(options=options)
    driver.set_window_size(1920,1080)

    return driver

# ================= GIT PUSH =================
def push_to_github():
    try:
        subprocess.run(["git", "config", "--global", "user.email", "bot@github.com"])
        subprocess.run(["git", "config", "--global", "user.name", "github-actions"])

        subprocess.run(["git", "add", "."])
        subprocess.run(["git", "commit", "-m", "update data"], check=False)
        subprocess.run(["git", "push"])
    except Exception as e:
        print("Git push error:", e)

# ================= MAIN =================
def main():
    file_exists = os.path.isfile(CSV_PATH)

    csv_file = open(CSV_PATH,"a",newline="",encoding="utf-8-sig")
    writer = csv.writer(csv_file)

    if not file_exists:
        writer.writerow(["station","date","time","benzene","butadiene"])

    saved_records = get_saved_records()

    write_log(f"📌 Loaded {len(saved_records)} existing records")
    write_log(f"💾 CSV PATH: {CSV_PATH}")
    write_log(f"📝 LOG PATH: {LOG_PATH}")

    driver = None

    try:
        write_log("🚀 START PROGRAM")

        driver = create_driver()
        driver.get(URL)

        wait = WebDriverWait(driver,20)

        wait.until(
            EC.presence_of_element_located(
                (By.CLASS_NAME,"leaflet-marker-icon"))
        )

        markers = driver.find_elements(By.CLASS_NAME,"leaflet-marker-icon")

        success_count = 0

        for marker in markers:
            for attempt in range(2):  # retry 2 ครั้ง
                try:
                    driver.execute_script(
                        "arguments[0].scrollIntoView(true);", marker)

                    driver.execute_script(
                        "arguments[0].click();", marker)

                    # รอ popup แทน sleep
                    WebDriverWait(driver,10).until(
                        EC.presence_of_element_located(
                            (By.CLASS_NAME,"leaflet-popup-content"))
                    )

                    station,date,time_data,benzene,butadiene = get_data(driver)

                    current_key = f"{station}_{date}_{time_data}"

                    if current_key in saved_records:
                        write_log(f"⏩ Skip duplicate: {station}")
                        break

                    if benzene is None and butadiene is None:
                        write_log(f"⚠️ No data: {station}")
                        break

                    writer.writerow([
                        station,
                        date,
                        time_data,
                        benzene,
                        butadiene
                    ])

                    csv_file.flush()

                    saved_records.add(current_key)
                    success_count += 1

                    write_log(
                        f"✅ {station} | BZ={benzene} | BD={butadiene}"
                    )

                    # ปิด popup
                    try:
                        close_btn = driver.find_element(By.CLASS_NAME, "leaflet-popup-close-button")
                        close_btn.click()
                    except:
                        pass

                    break

                except Exception as e:
                    if attempt == 1:
                        write_log(f"❌ Marker error: {e}")

        write_log(f"🎯 Finished | Saved {success_count} stations")

    except Exception as e:
        write_log(f"❌ MAIN ERROR: {e}")

    finally:
        csv_file.close()

        if driver:
            driver.quit()

        write_log("🛑 PROGRAM CLOSED")

# ================= RUN =================
if __name__ == "__main__":
    main()
    push_to_github()
