from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Login(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1,max_length=128)


class Register(Login):
    full_name: str = Field(min_length=2,max_length=100)
    phone: str = Field(pattern=r'^0\d{9}$')
    password: str = Field(min_length=8,max_length=128)
    gender: Literal['Nam','Nữ','Khác'] | None = None
    birth_year: int | None = Field(default=None,ge=1900,le=2026)

    @field_validator('full_name',mode='before')
    @classmethod
    def trim_name(cls,value):
        return value.strip() if isinstance(value,str) else value


class Profile(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    full_name: str = Field(min_length=2,max_length=100)
    phone: str = Field(pattern=r'^0\d{9}$')
    gender: Literal['Nam','Nữ','Khác'] = 'Khác'
    birth_year: int | None = Field(default=None,ge=1900,le=2026)
    avatar_url: str | None = Field(default=None,max_length=300)


class Address(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    recipient_name: str = Field(min_length=2,max_length=100)
    phone: str = Field(pattern=r'^0\d{9}$')
    province_id: int = Field(gt=0)
    detail: str = Field(min_length=8,max_length=300)
    label: Literal['Nhà riêng','Văn phòng'] = 'Nhà riêng'
    is_default: bool = False


class CartAdd(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(default=1,ge=1,le=99)


class CartUpdate(BaseModel):
    quantity: int = Field(ge=1,le=99)
    is_selected: bool = True


class CartSelection(BaseModel):
    is_selected: bool


class Checkout(BaseModel):
    address_id: int = Field(gt=0)
    voucher_code: str = Field(default='',max_length=40)
    use_coins: bool = False
    payment_method: Literal['COD','ShopeePay'] = 'COD'
    buy_now: CartAdd | None = None


class OrderCreate(Checkout):
    idempotency_key: str = Field(min_length=16,max_length=100,pattern=r'^[A-Za-z0-9_-]+$')
    expected_total: int | None = Field(default=None,ge=0)
    quote_token: str = Field(pattern=r'^[a-f0-9]{64}$')
