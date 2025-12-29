from django.contrib.auth.models import Group
from rest_framework import serializers

from ...models import Aviso


class AvisoSerializer(serializers.ModelSerializer):
    grupo_nome = serializers.CharField(source="grupo.name", read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.full_name", read_only=True
    )

    class Meta:
        model = Aviso
        fields = [
            "id",
            "titulo",
            "descricao",
            "grupo",
            "grupo_nome",
            "prioridade",
            "status",
            "data_inicio",
            "data_fim",
            "created_at",
            "updated_at",
            "created_by",
            "created_by_name",
            "updated_by",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]

    def validate_grupo(self, value):
        if value and value.name.lower() == "admin":
            raise serializers.ValidationError(
                "O grupo 'admin' não pode ser selecionado."
            )
        return value

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["created_by"] = request.user
            validated_data["updated_by"] = request.user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["updated_by"] = request.user
        return super().update(instance, validated_data)


class AvisoListSerializer(serializers.ModelSerializer):
    grupo_nome = serializers.CharField(source="grupo.name", read_only=True)

    class Meta:
        model = Aviso
        fields = [
            "id",
            "titulo",
            "descricao",
            "grupo",
            "grupo_nome",
            "prioridade",
            "status",
            "data_inicio",
            "data_fim",
            "created_at",
            "updated_at",
        ]


class AvisoOptionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ["id", "name"]
