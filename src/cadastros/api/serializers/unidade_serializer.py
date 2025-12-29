from rest_framework import serializers

from ...models import Unidade


class UnidadeSerializer(serializers.ModelSerializer):
    morador_nome = serializers.SerializerMethodField(read_only=True)
    identificacao_completa = serializers.CharField(read_only=True)

    class Meta:
        model = Unidade
        fields = [
            "id",
            "numero",
            "bloco",
            "morador_nome",
            "identificacao_completa",
            "is_active",
            "created_by",
            "updated_by",
            "created_on",
            "updated_on",
        ]
        read_only_fields = [
            "id",
            "created_on",
            "updated_on",
            "created_by",
            "updated_by",
        ]

    def get_morador_nome(self, obj):
        """Retorna o nome do morador associado à unidade via related_name"""
        try:
            # 'morador' é a relação reversa de User.unidade (RelatedManager)
            if hasattr(obj, "morador") and obj.morador is not None:
                first = obj.morador.all().first()
                if first:
                    return first.full_name
        except Exception:
            pass
        return None


class UnidadeListSerializer(serializers.ModelSerializer):
    morador_nome = serializers.SerializerMethodField(read_only=True)
    identificacao_completa = serializers.CharField(read_only=True)

    class Meta:
        model = Unidade
        fields = [
            "id",
            "numero",
            "bloco",
            "morador_nome",
            "identificacao_completa",
            "is_active",
            "created_on",
            "updated_on",
        ]

    def get_morador_nome(self, obj):
        """Retorna o nome do morador associado à unidade via related_name"""
        try:
            # 'morador' é a relação reversa de User.unidade (RelatedManager)
            if hasattr(obj, "morador") and obj.morador is not None:
                first = obj.morador.all().first()
                if first:
                    return first.full_name
        except Exception:
            pass
        return None


class UnidadeCreateBulkSerializer(serializers.Serializer):
    """Serializer para criação em lote de unidades"""

    unidades = serializers.ListField(
        child=serializers.DictField(), min_length=1
    )

    def validate_unidades(self, value):
        for unidade_data in value:
            if "numero" not in unidade_data:
                raise serializers.ValidationError(
                    "Cada unidade deve ter um número."
                )
        return value

    def create(self, validated_data):
        unidades_data = validated_data.get("unidades", [])
        created_unidades = []

        for unidade_data in unidades_data:
            unidade = Unidade.objects.create(**unidade_data)
            created_unidades.append(unidade)

        return created_unidades
