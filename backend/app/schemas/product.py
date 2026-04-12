from pydantic import BaseModel

class ProductCreate(BaseModel):
    name: str
    price: float
    stock: int
    image: str | None = None

class ProductOut(BaseModel):
    id: int
    name: str
    price: float
    stock: int
    image: str | None

    class Config:
        orm_mode = True