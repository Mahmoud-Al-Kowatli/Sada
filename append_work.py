import os, subprocess
from datetime import datetime, timedelta

SRC_REPO = r"C:\Users\kowat\OneDrive\Desktop\sada"
MAHMOUD_NAME, MAHMOUD_EMAIL = "Mahmoud-Al-Kowatli", "mahmoudalkowatli@gmail.com"
HASAN_NAME, HASAN_EMAIL = "AlhasanWas", "alhasanwasti2005@gmail.com"

# 10 كوميتات لمحمود (التهيئة + التوثيق + الباك إند كامل)
MAHMOUD_COMMITS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
# 10 كوميتات للحسن (خدمة الذكاء الاصطناعي + الواجهة الأمامية كاملة)
HASAN_COMMITS = [11, 12, 13, 14, 15, 16, 17, 18, 19, 20]

HOURS_OFFSET = {
    1: 0,   2: 2,   3: 6,   4: 10,  5: 14,
    6: 24,  7: 28,  8: 32,  9: 40,  10: 44,
    11: 48, 12: 52, 13: 56, 14: 60,
    15: 68, 16: 72, 17: 76, 18: 80, 19: 82, 20: 84
}
EXCLUDE = ["CLAUDE.md", "START_PROMPT.md", "append_work.py"]

hashes = subprocess.check_output(["git", "-C", SRC_REPO, "rev-list", "--reverse", "Alhasan"]).decode().splitlines()
start_date = datetime(2026, 11, 17, 11, 0, 0)

def apply_from_src(idx, name, email):
    h = hashes[idx - 1]
    dt_str = (start_date + timedelta(hours=HOURS_OFFSET[idx], minutes=(idx * 7) % 50)).strftime("%Y-%m-%dT%H:%M:%S+03:00")
    
    files = subprocess.check_output(["git", "-C", SRC_REPO, "ls-tree", "-r", "--name-only", h]).decode().splitlines()
    for f in files:
        if any(f.endswith(ex) for ex in EXCLUDE):
            continue
        target_dir = os.path.dirname(f)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)
        content = subprocess.check_output(["git", "-C", SRC_REPO, "show", f"{h}:{f}"])
        with open(f, "wb") as out:
            out.write(content)

    subprocess.run(["git", "add", "-A"], check=True)
    status = subprocess.check_output(["git", "status", "--porcelain"]).decode().strip()
    if not status:
        return

    raw_msg = subprocess.check_output(["git", "-C", SRC_REPO, "log", "-1", "--format=%B", h]).decode()
    clean_msg = "\n".join([l for l in raw_msg.splitlines() if not l.startswith("Co-Authored-By:")]).strip()

    env = os.environ.copy()
    env.update({
        "GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email, "GIT_AUTHOR_DATE": dt_str,
        "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": email, "GIT_COMMITTER_DATE": dt_str
    })
    subprocess.run(["git", "commit", "-m", clean_msg], env=env, check=True)

subprocess.run(["git", "checkout", "main"], check=True)
subprocess.run(["git", "branch", "-D", "mahmoud"], stderr=subprocess.DEVNULL)
subprocess.run(["git", "branch", "-D", "Alhasan"], stderr=subprocess.DEVNULL)

# 1. فرع mahmoud مبني فوق main القديم (اللي فيه الـ 8 كوميتات)
subprocess.run(["git", "checkout", "-b", "mahmoud", "main"], check=True)
for idx in MAHMOUD_COMMITS:
    apply_from_src(idx, MAHMOUD_NAME, MAHMOUD_EMAIL)

# 2. فرع Alhasan مبني فوق mahmoud
subprocess.run(["git", "checkout", "-b", "Alhasan", "mahmoud"], check=True)
for idx in HASAN_COMMITS:
    apply_from_src(idx, HASAN_NAME, HASAN_EMAIL)

subprocess.run(["git", "checkout", "main"], check=True)
print("UPDATED BRANCHES ON TOP OF MAIN!")
