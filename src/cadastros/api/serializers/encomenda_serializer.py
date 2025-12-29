from rest_framework import serializers

from ...models import Encomenda, Unidade


class EncomendaSerializer(serializers.ModelSerializer):
    unidade_identificacao = serializers.CharField(
        source="unidade.identificacao_completa", read_only=True
    )
    unidade_id = serializers.IntegerField(write_only=True)
    foi_retirada = serializers.BooleanField(read_only=True)

    class Meta:
        model = Encomenda
        fields = [
            "id",
            "unidade",
            "unidade_identificacao",
            "unidade_id",
            "destinatario_nome",
            "descricao",
            "codigo_rastreio",
            "retirado_por",
            "retirado_em",
            "foi_retirada",
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
            "foi_retirada",
        ]

    def validate_unidade_id(self, value):
        try:
            unidade = Unidade.objects.get(id=value)
            if not unidade.is_active:
                raise serializers.ValidationError(
                    "A unidade selecionada está inativa."
                )
            return value
        except Unidade.DoesNotExist:
            raise serializers.ValidationError("Unidade não encontrada.")

    def create(self, validated_data):
        unidade_id = validated_data.pop("unidade_id")
        validated_data["unidade"] = Unidade.objects.get(id=unidade_id)
        # created_by será definido na view
        return super().create(validated_data)

    def update(self, instance, validated_data):
        unidade_id = validated_data.pop("unidade_id", None)
        if unidade_id:
            validated_data["unidade"] = Unidade.objects.get(id=unidade_id)
        # updated_by será definido na view
        return super().update(instance, validated_data)


class EncomendaListSerializer(serializers.ModelSerializer):
    unidade_identificacao = serializers.CharField(
        source="unidade.identificacao_completa", read_only=True
    )
    foi_retirada = serializers.BooleanField(read_only=True)

    class Meta:
        model = Encomenda
        fields = [
            "id",
            "unidade",
            "unidade_identificacao",
            "destinatario_nome",
            "descricao",
            "codigo_rastreio",
            "retirado_por",
            "retirado_em",
            "foi_retirada",
            "created_on",
            "updated_on",
        ]
