from access.models import User
from rest_framework import serializers

from ...models import Visitante


class VisitanteSerializer(serializers.ModelSerializer):
    morador_nome = serializers.CharField(
        source="morador.full_name", read_only=True
    )
    morador_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(groups__name="Moradores"),
        source="morador",
        write_only=True,
    )
    esta_no_condominio = serializers.BooleanField(read_only=True)

    class Meta:
        model = Visitante
        fields = [
            "id",
            "nome",
            "documento",
            "placa_veiculo",
            "data_entrada",
            "data_saida",
            "is_permanente",
            "morador",
            "morador_nome",
            "morador_id",
            "esta_no_condominio",
            "created_on",
            "updated_on",
        ]
        read_only_fields = [
            "id",
            "morador",
            "created_on",
            "updated_on",
            "esta_no_condominio",
        ]

    def validate_placa_veiculo(self, value):
        """Valida e normaliza a placa do veículo"""
        if value:
            # Normalizar: remover hífen, espaços e converter para maiúsculas
            placa = value.strip().upper().replace("-", "").replace(" ", "")
            return placa
        return value

    def create(self, validated_data):
        # `morador_id` é tratado pelo PrimaryKeyRelatedField e populado como `morador`
        return super().create(validated_data)

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)


class VisitanteListSerializer(serializers.ModelSerializer):
    morador_nome = serializers.CharField(
        source="morador.full_name", read_only=True
    )
    esta_no_condominio = serializers.BooleanField(read_only=True)

    class Meta:
        model = Visitante
        fields = [
            "id",
            "nome",
            "documento",
            "placa_veiculo",
            "data_entrada",
            "data_saida",
            "is_permanente",
            "morador_nome",
            "esta_no_condominio",
            "created_on",
            "updated_on",
        ]
