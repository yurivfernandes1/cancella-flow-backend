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
            "email",
            "placa_veiculo",
            "qr_token",
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
            "qr_token",
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
    morador_unidade_bloco = serializers.SerializerMethodField(read_only=True)
    morador_unidade_numero = serializers.SerializerMethodField(read_only=True)
    morador_unidade_identificacao = serializers.SerializerMethodField(
        read_only=True
    )

    def _first_unidade(self, obj):
        if not getattr(obj, "morador", None):
            return None
        try:
            return obj.morador.unidades.first()
        except Exception:
            return None

    def get_morador_unidade_bloco(self, obj):
        unidade = self._first_unidade(obj)
        return getattr(unidade, "bloco", None) if unidade else None

    def get_morador_unidade_numero(self, obj):
        unidade = self._first_unidade(obj)
        return getattr(unidade, "numero", None) if unidade else None

    def get_morador_unidade_identificacao(self, obj):
        unidade = self._first_unidade(obj)
        if not unidade:
            return None
        return getattr(unidade, "identificacao_completa", None)

    class Meta:
        model = Visitante
        fields = [
            "id",
            "nome",
            "documento",
            "email",
            "placa_veiculo",
            "qr_token",
            "data_entrada",
            "data_saida",
            "is_permanente",
            "morador_nome",
            "morador_unidade_bloco",
            "morador_unidade_numero",
            "morador_unidade_identificacao",
            "esta_no_condominio",
            "created_on",
            "updated_on",
        ]
