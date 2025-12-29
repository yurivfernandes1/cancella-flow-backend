from access.models import User
from rest_framework import serializers


class UserMinimalSerializer(serializers.ModelSerializer):
    """Serializer mínimo com apenas id, full_name e username do usuário."""

    class Meta:
        model = User
        fields = ("id", "full_name", "username")
