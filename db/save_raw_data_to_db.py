from pydantic import BaseModel, field_validator
from typing import Any
from datetime import date




class User(BaseModel):
    id:int
    source: str
    source_url: str
    scraped_at: date
    scraper_version: str
    batch_id: str
    raw_data: dict[str, Any]
    ingestion_status: str
    created_at: date
    


user = User(
    name="wakil",
    age=2,
    is_user=True,
    message="This is the user"
)

print(user)
