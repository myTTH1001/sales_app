from pydantic import BaseModel

class AddItemSchema(BaseModel):
    product_id: int
    quantity: int = 1

class UpdateItemSchema(BaseModel):
    quantity: int
