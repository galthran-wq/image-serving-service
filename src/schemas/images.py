from pydantic import BaseModel


class ImageUploadRequest(BaseModel):
    data: str


class ImageUploadResponse(BaseModel):
    image_id: str
    url: str


class ImageDeleteResponse(BaseModel):
    deleted_count: int


class ImageFetchRequest(BaseModel):
    url: str
    pool: str | None = None


class ImageFetchResponse(BaseModel):
    data: str
    mime_type: str
