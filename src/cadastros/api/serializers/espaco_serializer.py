from django.contrib.auth import get_user_model
from rest_framework import serializers

from ...models import Espaco, EspacoInventarioItem, EspacoReserva

User = get_user_model()


class EspacoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Espaco
        fields = [
            "id",
            "nome",
            "capacidade_pessoas",
            "valor_aluguel",
            "is_active",
            "created_on",
            "updated_on",
            "created_by",
            "updated_by",
        ]
        read_only_fields = [
            "id",
            "created_on",
            "updated_on",
            "created_by",
            "updated_by",
        ]


class EspacoListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Espaco
        fields = [
            "id",
            "nome",
            "capacidade_pessoas",
            "valor_aluguel",
            "is_active",
            "created_on",
        ]


class EspacoInventarioItemSerializer(serializers.ModelSerializer):
    espaco_nome = serializers.CharField(source="espaco.nome", read_only=True)

    class Meta:
        model = EspacoInventarioItem
        fields = [
            "id",
            "espaco",
            "espaco_nome",
            "nome",
            "codigo",
            "is_active",
            "created_on",
            "updated_on",
            "created_by",
            "updated_by",
        ]
        read_only_fields = [
            "id",
            "espaco_nome",
            "created_on",
            "updated_on",
            "created_by",
            "updated_by",
        ]


class EspacoInventarioItemListSerializer(serializers.ModelSerializer):
    espaco_nome = serializers.CharField(source="espaco.nome", read_only=True)

    class Meta:
        model = EspacoInventarioItem
        fields = ["id", "espaco", "espaco_nome", "nome", "codigo", "is_active"]


class EspacoReservaSerializer(serializers.ModelSerializer):
    espaco_nome = serializers.CharField(source="espaco.nome", read_only=True)
    espaco_valor = serializers.DecimalField(
        source="espaco.valor_aluguel",
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    morador_nome = serializers.CharField(
        source="morador.get_full_name", read_only=True
    )
    morador_email = serializers.EmailField(
        source="morador.email", read_only=True
    )

    class Meta:
        model = EspacoReserva
        fields = [
            "id",
            "espaco",
            "espaco_nome",
            "espaco_valor",
            "morador",
            "morador_nome",
            "morador_email",
            "data_reserva",
            "valor_cobrado",
            "status",
            "created_on",
            "updated_on",
            "created_by",
            "updated_by",
        ]
        read_only_fields = [
            "id",
            "espaco_nome",
            "espaco_valor",
            "morador_nome",
            "morador_email",
            "created_on",
            "updated_on",
            "created_by",
            "updated_by",
        ]
        extra_kwargs = {
            "morador": {
                "required": False
            },  # Torna opcional, será preenchido automaticamente
        }

    def validate(self, data):
        # Validar que o morador está autenticado (apenas para criação)
        request = self.context.get("request")
        if request and request.user and not self.instance:
            # Apenas preencher morador em criação
            data["morador"] = request.user

        # Copiar o valor do aluguel do espaço para a reserva (apenas se espaço foi fornecido)
        if "espaco" in data:
            data["valor_cobrado"] = data["espaco"].valor_aluguel

        return data


class EspacoReservaListSerializer(serializers.ModelSerializer):
    espaco_nome = serializers.CharField(source="espaco.nome", read_only=True)
    espaco_valor = serializers.DecimalField(
        source="espaco.valor_aluguel",
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    morador_nome = serializers.CharField(
        source="morador.get_full_name", read_only=True
    )
    unidade = serializers.SerializerMethodField()

    class Meta:
        model = EspacoReserva
        fields = [
            "id",
            "espaco",
            "espaco_nome",
            "espaco_valor",
            "morador",
            "morador_nome",
            "unidade",
            "data_reserva",
            "valor_cobrado",
            "status",
        ]

    def get_unidade(self, obj):
        # Retornar a unidade do morador se existir
        morador = getattr(obj, "morador", None)
        if morador is None:
            return "-"

        # User possui FK 'unidade' no model (pode ser None)
        unidade = getattr(morador, "unidade", None)
        if unidade:
            return unidade.identificacao_completa
        return "-"
