from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .serializers import (
    LoginSerializer,
    RegisterSerializer,
    UpdateProfileSerializer,
    UserDetailSerializer,
)


class RegisterView(generics.CreateAPIView):
    """
    POST /api/v1/auth/register/
    Создаёт пользователя и возвращает JWT-пару.
    """

    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        # to_representation в сериализаторе возвращает {user, access, refresh}
        data = serializer.to_representation(user)
        return Response(data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """
    POST /api/v1/auth/login/
    Аутентификация по email + паролю, возвращает JWT-пару.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.to_representation(None)
        return Response(data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """
    POST /api/v1/auth/logout/
    Инвалидирует refresh-токен (добавляет в blacklist).
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"detail": "Refresh token обязателен."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            return Response(
                {"detail": "Токен недействителен или уже отозван."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"detail": "Успешный выход."}, status=status.HTTP_200_OK)


class MeView(generics.RetrieveUpdateAPIView):
    """
    GET  /api/v1/auth/me/  — получить свой профиль
    PATCH /api/v1/auth/me/ — обновить профиль
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return UpdateProfileSerializer
        return UserDetailSerializer

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        kwargs["partial"] = True    # всегда частичное обновление
        return super().update(request, *args, **kwargs)


class TokenRefreshView(TokenRefreshView):
    """
    POST /api/v1/auth/token/refresh/
    Стандартный simplejwt refresh с нашей обёрткой (можно расширить).
    """
    pass
