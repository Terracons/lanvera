from app.config.oauth import oauth
from starlette.responses import RedirectResponse
from fastapi import (
    APIRouter, Depends, HTTPException, BackgroundTasks, Request, status, Form, Query
)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from datetime import timedelta
import os
import logging

from app.database import get_db
from app.schemas.schemas import UserCreate, UserOut, ForgotPasswordRequest, Token, BecomeAgency, UpdateProfile,LoginSchema
from app.models.models import User
from app.security import hash_password, verify_password, create_access_token, get_current_user
from app.services.email import send_email_verification, send_welcome_email, send_reset_password_email
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))

router = APIRouter(prefix="/auth", tags=["Auth"])
templates = Jinja2Templates(directory="app/templates")

from dotenv import load_dotenv
load_dotenv()

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

@router.post("/signup", response_model=UserOut)
def signup(user_data: UserCreate, request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        username=user_data.username,
        email=user_data.email,
        phone = user_data.phone,
        password=hash_password(user_data.password),
        is_verified=False
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    background_tasks.add_task(send_email_verification, new_user, request)
    logger.info("Signup: verification email sent to %s", new_user.email)

    return new_user

@router.get("/confirm-email/{token}", response_class=HTMLResponse)
def confirm_email(request: Request, token: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("email")

        if not email:
            raise ValueError("Missing email in token")

        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise ValueError("User not found")
        if user.is_verified:
            status_msg = ("info", "Email already verified")
        else:
            user.is_verified = True
            db.commit()
            background_tasks.add_task(send_welcome_email, user.email, db, background_tasks)
            status_msg = ("success", "Email verified successfully!")

        return templates.TemplateResponse("email_confirmation.html", {
         "request": request,
         "status": status_msg[0],
         "message": status_msg[1],
        "frontend_url": os.getenv("FRONTEND_URL", "http://localhost:5173")
        })

    except (JWTError, ValueError) as e:
        logger.warning("Email confirmation failed: %s", str(e))
        return templates.TemplateResponse("email_confirmation.html", {
            "request": request, "status": "error", "message": "Invalid or expired token"
        })
@router.get("/google-login")
async def google_login(request: Request):
    redirect_uri = request.url_for('google_callback')
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/login-google", response_class=HTMLResponse)
async def login_google_page(request: Request):
    return templates.TemplateResponse("google_login.html", {"request": request})


@router.get("/google-callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get("userinfo") or await oauth.google.userinfo(request, token=token)

        if not user_info:
            raise HTTPException(status_code=400, detail="User info not available from Google")

        email = user_info["email"]
        username = user_info.get("name", email.split('@')[0])

        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                username=username,
                email=email,
                password=hash_password(os.urandom(8).hex()),
                is_verified=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        access_token = create_access_token(
            data={"sub": user.email},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )

        # ✅ Redirect to your frontend with token in query param
        redirect_url = f"{FRONTEND_URL}/login-success?token={access_token}"
        return RedirectResponse(url=redirect_url)

    except Exception as e:
        logger.error("Google auth failed: %s", str(e))
        raise HTTPException(status_code=400, detail="Google login failed")

@router.post("/login", response_model=Token)
def login(data: LoginSchema, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Please verify your email first")

    token = create_access_token(
        {"sub": user.email}, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    logger.info("Login: %s", user.email)
    return {"access_token": token, "token_type": "bearer"}

@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()

    if user:
        reset_token = create_access_token({"sub": user.email}, timedelta(minutes=30))
        background_tasks.add_task(send_reset_password_email, user.email, db, reset_token)
        logger.info("Password reset token sent to %s", user.email)

    return {"message": "If an account with that email exists, a reset link has been sent."}

@router.api_route("/reset-password", methods=["GET", "POST"], response_class=HTMLResponse)
async def reset_password(
    request: Request,
    db: Session = Depends(get_db),
    token: str = Query(None),
    new_password: str = Form(None)
):
    if request.method == "GET":
        return templates.TemplateResponse("reset_password.html", {"request": request, "token": token})

    form_data = await request.form()
    token = form_data.get("token")
    new_password = form_data.get("new_password")

    if not token or not new_password:
        raise HTTPException(status_code=400, detail="Invalid request")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_email = payload.get("sub")
        if not user_email:
            raise ValueError("Invalid token payload")
    except (JWTError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password = hash_password(new_password)
    db.commit()
    logger.info("Password reset successful for %s", user.email)
    return RedirectResponse(url="/auth/login", status_code=303)


@router.post("/become-agency")
def become_agency(data: BecomeAgency, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role == "agency":
        raise HTTPException(status_code=400, detail="User is already an agency")

    current_user.role = "agency"
    current_user.agency_name = data.agency_name
    current_user.agency_address = data.agency_address

    db.commit()
    db.refresh(current_user)

    return {"message": "You are now registered as an agency", "role": current_user.role}

@router.put("/update-profile", response_model=UserOut)
def update_profile(
    data: UpdateProfile,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if data.username:
        current_user.username = data.username
    if data.email:
        current_user.email = data.email
    if data.agency_name:
        current_user.agency_name = data.agency_name
    if data.agency_address:
        current_user.agency_address = data.agency_address

    db.commit()
    db.refresh(current_user)

    return current_user


@router.get("/me", response_model=UserOut)
def get_current_profile(
    current_user: User = Depends(get_current_user)
):
    return current_user
