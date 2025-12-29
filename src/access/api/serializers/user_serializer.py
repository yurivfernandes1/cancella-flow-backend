from access.models import User
from rest_framework import serializers


class UserSerializer(serializers.ModelSerializer):
    condominio_nome = serializers.CharField(
        source="condominio.nome", read_only=True
    )
    condominio_id = serializers.IntegerField(
        source="condominio.id", read_only=True
    )
    unidade_identificacao = serializers.CharField(
        source="unidade.identificacao_completa",
        read_only=True,
        allow_null=True,
    )
    unidade_id = serializers.IntegerField(
        write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "full_name",
            "cpf",
            "phone",
            "first_access",
            "is_staff",
            "is_active",
            "created_at",
            "updated_at",
            "condominio",
            "condominio_nome",
            "condominio_id",
            "unidade",
            "unidade_identificacao",
            "unidade_id",
        )
