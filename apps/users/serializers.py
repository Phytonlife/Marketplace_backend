from django.contrib.auth import authenticate, get_user_model
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import MasterProfile

User = get_user_model()


# ─── Master Profile ───────────────────────────────────────────────────────────

class MasterProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = MasterProfile
        fields = [
            "description",
            "city",
            "rating",
            "review_count",
            "is_verified",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["rating", "review_count", "is_verified", "created_at", "updated_at"]


# ─── User Detail (GET /me/) ───────────────────────────────────────────────────

class UserDetailSerializer(serializers.ModelSerializer):
    """Полный профиль текущего пользователя."""

    master_profile = MasterProfileSerializer(read_only=True)
    full_name = serializers.CharField(read_only=True)
    avatar = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "full_name",
            "phone_number",
            "role",
            "avatar",
            "date_joined",
            "master_profile",
        ]
        read_only_fields = ["id", "email", "date_joined", "full_name"]


# ─── Registration ─────────────────────────────────────────────────────────────

class RegisterSerializer(serializers.Serializer):
    """Регистрация нового пользователя с выдачей JWT-пары."""

    email = serializers.EmailField(required=True)
    username = serializers.CharField(max_length=150, required=True)
    password = serializers.CharField(write_only=True, min_length=8, style={"input_type": "password"})
    password_confirm = serializers.CharField(write_only=True, style={"input_type": "password"})
    first_name = serializers.CharField(max_length=150, required=False, default="")
    last_name = serializers.CharField(max_length=150, required=False, default="")
    phone_number = serializers.CharField(max_length=17, required=False, allow_blank=True)
    role = serializers.ChoiceField(
        choices=["client", "master"],   # admin нельзя выбрать при регистрации
        default="client",
    )

    def save(self, request=None, **kwargs):
        """
        Перехватываем аргумент request от библиотеки dj-rest-auth,
        чтобы избежать ошибки TypeError (takes 1 positional argument but 2 were given).
        """
        return super().save(**kwargs)
    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(_("Пользователь с таким email уже зарегистрирован."))
        return value.lower()

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError(_("Это имя пользователя уже занято."))
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError({"password_confirm": _("Пароли не совпадают.")})
        return attrs

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data["email"],
            username=validated_data["username"],
            password=validated_data["password"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
            phone_number=validated_data.get("phone_number") or None,
            role=validated_data.get("role", "client"),
        )
        return user

    def to_representation(self, instance):
        """После сохранения возвращаем JWT + данные пользователя."""
        refresh = RefreshToken.for_user(instance)
        return {
            "user": UserDetailSerializer(instance, context=self.context).data,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }


# ─── Login ────────────────────────────────────────────────────────────────────

class LoginSerializer(serializers.Serializer):
    """Email + пароль → JWT-пара."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, attrs):
        email = attrs.get("email", "").lower()
        password = attrs.get("password")

        user = authenticate(request=self.context.get("request"), email=email, password=password)

        if not user:
            raise serializers.ValidationError(_("Неверный email или пароль."), code="authorization")

        if not user.is_active:
            raise serializers.ValidationError(_("Аккаунт заблокирован."), code="authorization")

        attrs["user"] = user
        return attrs

    def to_representation(self, instance):
        user = self.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        return {
            "user": UserDetailSerializer(user, context=self.context).data,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }


# ─── Update Profile ───────────────────────────────────────────────────────────

class UpdateProfileSerializer(serializers.ModelSerializer):
    """PATCH /api/v1/auth/me/ — изменение профиля."""

    master_profile = MasterProfileSerializer(required=False)

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "phone_number",
            "avatar",
            "master_profile",
        ]

    def update(self, instance, validated_data):
        master_data = validated_data.pop("master_profile", None)

        # Обновляем поля пользователя
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Обновляем профиль мастера, если данные переданы
        if master_data and instance.is_master:
            profile, _ = MasterProfile.objects.get_or_create(user=instance)
            for attr, value in master_data.items():
                setattr(profile, attr, value)
            profile.save()

        return instance
