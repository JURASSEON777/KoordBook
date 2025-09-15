# test_imports.py
try:
    import telegram
    print("✅ telegram installed")
except ImportError:
    print("❌ telegram not found")

try:
    import gspread
    print("✅ gspread installed")
except ImportError:
    print("❌ gspread not found")

try:
    from google.oauth2 import service_account
    print("✅ google-auth installed")
except ImportError:
    print("❌ google-auth not found")

try:
    from googleapiclient import discovery
    print("✅ googleapiclient installed")
except ImportError:
    print("❌ googleapiclient not found")