from access.models import User
from rest_framework import serializers

from ...models import Visitante


class VisitanteSerializer(serializers.ModelSerializer):
    morador_nome = serializers.CharField(
        source="morador.full_name", read_only=True
    )
    morador_id = serializers.IntegerField(write_only=True)
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

    def validate_morador_id(self, value):
        try:
            morador = User.objects.get(id=value)
            if not morador.groups.filter(name="Moradores").exists():
                raise serializers.ValidationError(
                    "O usuário selecionado não é um morador."
                )
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("Morador não encontrado.")

    def create(self, validated_data):
        morador_id = validated_data.pop("morador_id")
        validated_data["morador"] = User.objects.get(id=morador_id)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        morador_id = validated_data.pop("morador_id", None)
        if morador_id:
            validated_data["morador"] = User.objects.get(id=morador_id)
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
