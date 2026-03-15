from access.models import User
from django.contrib.auth.models import Group
from rest_framework import serializers


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ["id", "name"]


class UserListSerializer(serializers.ModelSerializer):
    condominio_nome = serializers.CharField(
        source="condominio.nome", read_only=True
    )
    condominio_id = serializers.IntegerField(
        source="condominio.id", read_only=True
    )
    unidade_identificacao = serializers.SerializerMethodField(read_only=True)
    unidade_id = serializers.SerializerMethodField(read_only=True)

    def get_unidade_identificacao(self, obj):
        first = obj.unidades.first()
        return first.identificacao_completa if first else None

    def get_unidade_id(self, obj):
        first = obj.unidades.first()
        return str(first.id) if first else None

    groups = GroupSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "full_name",
            "cpf",
            "phone",
            "is_staff",
            "is_active",
            "created_at",
            "updated_at",
            "condominio_nome",
            "condominio_id",
            "unidade_identificacao",
            "unidade_id",
            "groups",
        ]
