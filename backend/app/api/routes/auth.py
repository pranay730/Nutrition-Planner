from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import DatabaseSession
from app.auth.schemas import AuthResponse, LoginRequest, RegisterRequest
from app.auth.service import AuthService, EmailAlreadyRegisteredError, InvalidCredentialsError

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: DatabaseSession) -> AuthResponse:
    try:
        user, token = AuthService(db).register(str(payload.email), payload.password)
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from exc
    return AuthResponse(access_token=token, user=user)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: DatabaseSession) -> AuthResponse:
    try:
        user, token = AuthService(db).login(str(payload.email), payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return AuthResponse(access_token=token, user=user)
