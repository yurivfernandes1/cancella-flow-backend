from access.models import User
from rest_framework import serializers

from ...models import Veiculo


class VeiculoSerializer(serializers.ModelSerializer):
    morador_nome = serializers.CharField(
        source="morador.full_name", read_only=True
    )
    morador_id = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = Veiculo
        fields = [
            "id",
            "placa",
            "marca_modelo",
            "morador",
            "morador_nome",
            "morador_id",
            "is_active",
            "created_by",
            "updated_by",
            "created_on",
            "updated_on",
        ]
        read_only_fields = [
            "id",
            "morador",
            "created_on",
            "updated_on",
            "created_by",
            "updated_by",
        ]

    def validate_placa(self, value):
        """Valida e normaliza a placa"""
        if value:
            # Normalizar: remover hífen, espaços e converter para maiúsculas
            placa = value.strip().upper().replace("-", "").replace(" ", "")

            # Validação já ocorre no model, mas podemos retornar normalizada
            return placa
        return value

    def create(self, validated_data):
        morador_id = validated_data.pop("morador_id", None)

        # Se morador_id foi fornecido, usar ele; senão usar o usuário autenticado
        if morador_id:
            validated_data["morador"] = User.objects.get(id=morador_id)
        elif "morador" not in validated_data:
            # Se não forneceu morador_id nem morador, usar o request.user (será definido na view)
            pass

        return super().create(validated_data)

    def update(self, instance, validated_data):
        morador_id = validated_data.pop("morador_id", None)

        if morador_id:
            validated_data["morador"] = User.objects.get(id=morador_id)

        return super().update(instance, validated_data)


class VeiculoListSerializer(serializers.ModelSerializer):
    morador_nome = serializers.CharField(
        source="morador.full_name", read_only=True
    )

    class Meta:
        model = Veiculo
        fields = [
            "id",
            "placa",
            "marca_modelo",
            "morador_nome",
            "is_active",
            "created_on",
        ]
