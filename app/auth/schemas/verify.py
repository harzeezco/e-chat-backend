from pydantic import BaseModel


class VerifyRequest(BaseModel):
    token: str
