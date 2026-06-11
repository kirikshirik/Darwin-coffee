import re

with open('backend/dashboard.py', 'r') as f:
    content = f.read()

# Patch _overview definition
old_ov_def = "def _overview() -> dict:"
new_ov_def = """def _overview(period_str: str = "7d") -> dict:
    today = date.today()
    end = datetime(today.year, today.month, today.day) + timedelta(days=1)
    
    if period_str == "вч":
        end = end - timedelta(days=1)
        start = end - timedelta(days=1)
        prev_start = start - timedelta(days=1)
        label_text = "вчера"
        days_count = 1
    elif period_str == "мес":
        start = end - timedelta(days=30)
        prev_start = start - timedelta(days=30)
        label_text = "30 дней"
        days_count = 30
    else: # 7д
        start = end - timedelta(days=7)
        prev_start = start - timedelta(days=7)
        label_text = "7 дней"
        days_count = 7"""

content = re.sub(r"def _overview\(\) -> dict:\n    today = date\.today\(\)\n    end = datetime\(today\.year, today\.month, today\.day\) \+ timedelta\(days=1\)\n    start = end - timedelta\(days=7\)\n    prev_start = start - timedelta\(days=7\)", new_ov_def, content)

# Patch _overview checks label
content = content.replace('f"7 дней · {checks} чеков"', 'f"{label_text} · {checks} чеков"')
content = content.replace('f"{checks} чеков за 7 дней"', 'f"{checks} чеков за {label_text}"')

# Patch hnote
content = content.replace('выручки за 7 дней (пик)', 'выручки за {label_text} (пик)')

# Patch acquiring text
content = content.replace('расход\'', 'расход за {label_text}\'')

# Patch compute signature and _overview call
content = content.replace("def compute() -> dict:", "def compute(period_str: str = '7д') -> dict:")
content = content.replace("**_overview(),", "**_overview(period_str),")
content = content.replace("def build_html() -> str:", "def build_html(period_str: str = '7д') -> str:")
content = content.replace("return render(compute())", "return render(compute(period_str))")

with open('backend/dashboard.py', 'w') as f:
    f.write(content)

print("Patched dashboard.py")
