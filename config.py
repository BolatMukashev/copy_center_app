from dotenv import dotenv_values
import os


config = dotenv_values(".env")


R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID") or config.get('R2_ACCOUNT_ID')
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID") or config.get("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY") or config.get("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME") or config.get("R2_BUCKET_NAME")