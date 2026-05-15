from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Setting
from app.schemas.setting import SettingsRead, SettingsUpdate

DEFAULT_SETTINGS = {
    "llm_provider": "openai",
    "llm_model": "gpt-4.1-mini",
    "search_provider": "brave",
    "report_time": "08:00",
    "retention_days": 365,
}


def read_settings(db: Session) -> SettingsRead:
    env = get_settings()
    persisted = {row.key: row.value for row in db.query(Setting).all()}
    merged = {**DEFAULT_SETTINGS, **{key: value.get("value") for key, value in persisted.items()}}
    return SettingsRead(
        llm_provider=merged["llm_provider"],
        llm_model=merged["llm_model"],
        search_provider=merged["search_provider"],
        report_time=merged["report_time"],
        retention_days=int(merged["retention_days"]),
        api_key_status={
            "openai": bool(env.openai_api_key),
            "brave": bool(env.brave_search_api_key),
            "tavily": bool(env.tavily_api_key),
            "github": bool(env.github_token),
            "product_hunt": bool(env.product_hunt_token),
            "coingecko": bool(env.coingecko_api_key),
            "amazon_sp_api": bool(
                env.amazon_sp_api_client_id
                and env.amazon_sp_api_client_secret
                and env.amazon_sp_api_refresh_token
            ),
        },
    )


def update_settings(db: Session, patch: SettingsUpdate) -> SettingsRead:
    for key, value in patch.model_dump(exclude_unset=True).items():
        row = db.query(Setting).filter(Setting.key == key).first()
        if row:
            row.value = {"value": value}
        else:
            db.add(Setting(key=key, value={"value": value}, is_secret=False))
    db.commit()
    return read_settings(db)
