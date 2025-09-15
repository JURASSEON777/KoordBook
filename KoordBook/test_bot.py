import sys

print("Python path:", sys.path)
print("\n--- Testing imports ---")

try:
    import telegram

    print("✅ telegram import successful")
    print("Version:", telegram.__version__)
except ImportError as e:
    print("❌ telegram import failed:", e)

try:
    from telegram.ext import Application, Updater

    print("✅ telegram.ext import successful")

    # Test creating application
    app = Application.builder().token("dummy_token").build()
    print("✅ Application creation successful")

except Exception as e:
    print("❌ telegram.ext import failed:", e)
    print("Error type:", type(e).__name__)