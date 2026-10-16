import logging
import time
from contextlib import asynccontextmanager
from urllib.parse import urlsplit
from fastapi import FastAPI,Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from app import config
from app.database import initialize
from app.recommender.service import service
from app.routers import account,auth,cart,orders,products,recommendations

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app):
    initialize()
    service.load()
    logging.info('Shopee MUSE started: demo_mode=%s model_ready=%s',config.DEMO_MODE,bool(service.model))
    yield


app=FastAPI(title='Shopee MUSE',version='1.0.0',lifespan=lifespan,
            docs_url='/api/docs' if config.DEMO_MODE else None,redoc_url=None,
            openapi_url='/api/openapi.json' if config.DEMO_MODE else None)


@app.exception_handler(RequestValidationError)
async def invalid_input(request,exception):
    field=str(exception.errors()[0]['loc'][-1]) if exception.errors() else ''
    messages={
        'phone':'Số điện thoại cần gồm 10 chữ số và bắt đầu bằng 0.',
        'full_name':'Họ và tên cần có từ 2 đến 100 ký tự.',
        'recipient_name':'Tên người nhận cần có từ 2 đến 100 ký tự.',
        'quantity':'Vui lòng chọn số lượng từ 1 đến 99 sản phẩm.',
        'birth_year':'Vui lòng kiểm tra lại năm sinh.',
        'detail':'Địa chỉ cụ thể cần có từ 8 đến 300 ký tự.',
        'password':'Vui lòng kiểm tra độ dài mật khẩu đã nhập.',
        'new_password':'Mật khẩu mới cần có từ 8 đến 128 ký tự.',
        'address_id':'Vui lòng chọn địa chỉ nhận hàng.',
        'rating':'Vui lòng chọn đánh giá từ 1 đến 5 sao.',
        'content':'Nội dung đánh giá cần có từ 10 đến 1.000 ký tự.',
    }
    return JSONResponse({'detail':messages.get(field,'Thông tin chưa hợp lệ. Vui lòng kiểm tra lại các trường đã nhập.')},status_code=422)


@app.middleware('http')
async def security_headers(request:Request,call_next):
    start=time.perf_counter()
    if request.method not in ('GET','HEAD','OPTIONS'):
        origin=request.headers.get('origin')
        if request.headers.get('sec-fetch-site')=='cross-site' or (origin and urlsplit(origin).netloc!=request.headers.get('host')):
            return JSONResponse({'detail':'Nguồn yêu cầu không hợp lệ.'},status_code=403)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; style-src-attr 'unsafe-inline'; img-src 'self' https://salt.tikicdn.com https://*.tikicdn.com https://m.media-amazon.com https://images.unsplash.com data:; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'self'"
    response.headers['Server-Timing']=f'app;dur={(time.perf_counter()-start)*1000:.2f}'
    if request.url.path.startswith('/api/') and not request.url.path.startswith('/api/item-art/'):
        response.headers['Cache-Control']='no-store'
    return response


for router in (auth.router,account.router,products.router,cart.router,orders.router,recommendations.router):
    app.include_router(router)
app.mount('/static',StaticFiles(directory=config.ROOT/'static'),name='static')


@app.get('/api/health')
def health():
    return {'status':'ok','demo_mode':config.DEMO_MODE,'model_ready':service.model is not None,
            'recommendation_engine':service.status()['engine']}


@app.get('/',include_in_schema=False)
def index():
    return FileResponse(config.ROOT/'templates/index.html')
