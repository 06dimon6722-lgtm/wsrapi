from fastapi import Header, HTTPException, status


async def require_client_id(client_id: str = Header(..., alias="ClientId")) -> str:
    if not client_id.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ClientId обязателен")
    return client_id
