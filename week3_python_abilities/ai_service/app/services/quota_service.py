from datetime import date
from app.schemas.auth import UserRecord
from app.repositories.user_repo import update_user


DAILY_QUOTA_LIMIT = 3


def ensure_daily_quota(user: UserRecord) -> UserRecord:
  today = date.today()
  if user.quota_date != today:
    user.daily_quota = DAILY_QUOTA_LIMIT
    user.quota_date = today
    update_user(email=user.email, user=user)
  return user