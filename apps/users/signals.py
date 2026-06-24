from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import CustomUser, MasterProfile


@receiver(post_save, sender=CustomUser)
def create_or_update_master_profile(sender, instance: CustomUser, created: bool, **kwargs):
    """
    Автоматически создаёт MasterProfile, если роль пользователя — 'master'.
    При изменении роли обратно профиль остаётся (soft logic).
    """
    if instance.role == CustomUser.Role.MASTER:
        MasterProfile.objects.get_or_create(user=instance)
