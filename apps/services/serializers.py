from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Category, EventType, Service, ServiceImage

User = get_user_model()


# ─── EventType ────────────────────────────────────────────────────────────────

class EventTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model  = EventType
        fields = ["id", "name", "slug", "icon"]


# ─── ServiceImage ─────────────────────────────────────────────────────────────

class ServiceImageSerializer(serializers.ModelSerializer):
    """
    Сериализатор одного фото галереи.

    GET  → возвращает абсолютный URL через SerializerMethodField
    POST → принимает файл через multipart/form-data
    """

    image_url = serializers.SerializerMethodField()

    class Meta:
        model        = ServiceImage
        fields       = ["id", "image", "image_url", "is_main", "sort_order"]
        read_only_fields = ["id", "image_url"]
        extra_kwargs = {
            "image": {"write_only": True},   # принимаем файл, но отдаём image_url
        }

    def get_image_url(self, obj) -> str | None:
        request = self.context.get("request")
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url if obj.image else None


# ─── Category ─────────────────────────────────────────────────────────────────

class SubcategorySerializer(serializers.ModelSerializer):
    class Meta:
        model  = Category
        fields = ["id", "name", "slug", "icon"]


class CategorySerializer(serializers.ModelSerializer):
    subcategories = SubcategorySerializer(many=True, read_only=True)

    class Meta:
        model        = Category
        fields       = ["id", "name", "slug", "icon", "parent", "subcategories"]
        read_only_fields = ["slug"]


# ─── Master short card ────────────────────────────────────────────────────────

class MasterShortSerializer(serializers.ModelSerializer):
    """
    Компактная карточка исполнителя для вывода внутри услуги.
    Включает данные из MasterProfile без дополнительных запросов
    (при правильном select_related в queryset).
    """

    full_name    = serializers.CharField(read_only=True)
    avatar       = serializers.ImageField(read_only=True)
    city         = serializers.SerializerMethodField()
    city_display = serializers.SerializerMethodField()
    rating       = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    is_verified  = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = [
            "id", "full_name", "avatar",
            "city", "city_display",
            "rating", "review_count", "is_verified",
        ]

    def _profile(self, obj):
        return getattr(obj, "master_profile", None)

    def get_city(self, obj) -> str:
        p = self._profile(obj)
        return p.city if p else ""

    def get_city_display(self, obj) -> str:
        p = self._profile(obj)
        return p.get_city_display() if p else ""

    def get_rating(self, obj) -> float:
        p = self._profile(obj)
        return float(p.rating) if p else 0.0

    def get_review_count(self, obj) -> int:
        p = self._profile(obj)
        return p.review_count if p else 0

    def get_is_verified(self, obj) -> bool:
        p = self._profile(obj)
        return p.is_verified if p else False


# ─── Service — Read ───────────────────────────────────────────────────────────

class ServiceReadSerializer(serializers.ModelSerializer):
    """
    Полное представление услуги для GET-запросов.

    Поля:
      master          — карточка исполнителя (рейтинг, город, верификация)
      category        — категория
      event_types     — массив типов мероприятий [{id, name, slug, icon}]
      gallery         — полная галерея фото (related_name='gallery')
      main_image      — URL главного фото (для карточки каталога)
      video_url       — ссылка на видео-портфолио
      price_type_display — человекочитаемый тип цены
      priority_score  — аннотированный рейтинг алгоритма (из queryset, только list)
    """

    category          = SubcategorySerializer(read_only=True)
    master            = MasterShortSerializer(read_only=True)
    event_types       = EventTypeSerializer(many=True, read_only=True)
    gallery           = ServiceImageSerializer(many=True, read_only=True)
    price_type_display = serializers.CharField(
        source="get_price_type_display", read_only=True
    )
    main_image = serializers.SerializerMethodField()

    # priority_score аннотируется в get_queryset() только для list/retrieve;
    # default=None безопасен для новых объектов без аннотации
    priority_score = serializers.FloatField(read_only=True, default=None)

    class Meta:
        model  = Service
        fields = [
            "id",
            "master",
            "category",
            "event_types",
            "title",
            "description",
            "price",
            "price_type",
            "price_type_display",
            "min_duration",
            "cover_image",
            "main_image",
            "gallery",
            "video_url",
            "priority_score",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def get_main_image(self, obj) -> str | None:
        """
        Главное фото для карточки в каталоге.
        Порядок приоритетов: gallery(is_main) → cover_image → None.
        """
        request = self.context.get("request")
        url = obj.main_image_url
        if url and request:
            return request.build_absolute_uri(url)
        return url


# ─── Service — Write ──────────────────────────────────────────────────────────

class ServiceWriteSerializer(serializers.ModelSerializer):
    """
    Сериализатор для POST / PATCH /services/.

    Приём файлов галереи:
      Фронтенд отправляет multipart/form-data:
        images[0] = <File>
        images[1] = <File>
        ...
      create() итерирует request.FILES.getlist('images') и массово
      создаёт ServiceImage через bulk_create.

    Важно: первый загруженный файл автоматически становится is_main=True,
    если у услуги ещё нет главного фото.
    """

    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source="category",
    )
    event_type_ids = serializers.PrimaryKeyRelatedField(
        queryset=EventType.objects.all(),
        source="event_types",
        many=True,
        required=False,
    )
    master = serializers.HiddenField(
        default=serializers.CurrentUserDefault()
    )

    class Meta:
        model  = Service
        fields = [
            "id",
            "master",
            "category_id",
            "event_type_ids",
            "title",
            "description",
            "price",
            "price_type",
            "min_duration",
            "cover_image",
            "video_url",
            "is_active",
        ]
        read_only_fields = ["id"]

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Цена должна быть больше нуля.")
        return value

    def validate_video_url(self, value: str) -> str:
        """Принимаем только YouTube и Vimeo — защита от спама."""
        if value:
            allowed = ("youtube.com", "youtu.be", "vimeo.com", "rutube.ru")
            if not any(host in value for host in allowed):
                raise serializers.ValidationError(
                    "Допустимые видеохостинги: YouTube, Vimeo, RuTube."
                )
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        if self.instance and request and self.instance.master != request.user:
            raise serializers.ValidationError("Вы не можете редактировать чужую услугу.")
        return attrs

    def _bulk_create_images(self, service: Service, request) -> None:
        """
        Массовое создание ServiceImage из request.FILES.getlist('images').

        Алгоритм:
        1. Берём все файлы из поля 'images'
        2. Первый файл получает is_main=True (если у услуги нет главного фото)
        3. bulk_create → один INSERT вместо N × INSERT
        4. save() каждого объекта НЕ вызывается (bypass) — is_main
           устанавливается явно, без риска race condition в save().
        """
        if request is None:
            return

        image_files = request.FILES.getlist("images")
        if not image_files:
            return

        has_main = service.gallery.filter(is_main=True).exists()

        objects = []
        for idx, file in enumerate(image_files):
            # Первый файл → главное фото, если ещё нет ни одного
            make_main = (idx == 0) and (not has_main) and (not service.cover_image)
            objects.append(
                ServiceImage(
                    service=service,
                    image=file,
                    is_main=make_main,
                    sort_order=idx,
                )
            )

        # bulk_create не вызывает save() → не нужно беспокоиться об is_main логике
        ServiceImage.objects.bulk_create(objects)

    def create(self, validated_data):
        event_types = validated_data.pop("event_types", [])
        instance    = super().create(validated_data)

        if event_types:
            instance.event_types.set(event_types)

        # Загружаем фото галереи из request
        request = self.context.get("request")
        self._bulk_create_images(instance, request)

        return instance

    def update(self, instance, validated_data):
        event_types = validated_data.pop("event_types", None)
        instance    = super().update(instance, validated_data)

        if event_types is not None:
            instance.event_types.set(event_types)

        # При PATCH тоже можем добавлять новые фото
        request = self.context.get("request")
        self._bulk_create_images(instance, request)

        return instance

    def to_representation(self, instance):
        """После сохранения возвращаем полное Read-представление."""
        return ServiceReadSerializer(instance, context=self.context).data
