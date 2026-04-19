from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from jobs.models import Category

User = get_user_model()


@receiver(post_save, sender=User)
def create_default_category(sender, instance, created, **kwargs):
    if created:
        Category.objects.get_or_create(user=instance, name="Uncategorized")
