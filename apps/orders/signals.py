import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Review

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Review)
def update_master_rating_on_review(
    sender, instance: Review, created: bool, **kwargs
) -> None:
    """
    После создания нового отзыва автоматически пересчитывает
    скользящий рейтинг мастера через MasterProfile.update_rating().

    Обновление существующего отзыва не пересчитывает рейтинг
    (для MVP достаточно; в production нужен полный пересчёт).
    """
    if not created:
        return

    master = instance.master
    profile = getattr(master, "master_profile", None)

    if profile is None:
        logger.warning(
            "Review #%s: у мастера %s нет MasterProfile — рейтинг не обновлён.",
            instance.pk,
            master.email,
        )
        return

    try:
        profile.update_rating(float(instance.rating))
        logger.info(
            "Review #%s: рейтинг мастера %s обновлён → %.2f (%d отзывов).",
            instance.pk,
            master.email,
            profile.rating,
            profile.review_count,
        )
    except Exception as exc:
        logger.error(
            "Review #%s: ошибка обновления рейтинга мастера %s: %s",
            instance.pk,
            master.email,
            exc,
        )
