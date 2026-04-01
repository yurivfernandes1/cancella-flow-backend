from rest_framework import serializers

from ...models import EventoCerimonialConvite, EventoCerimonialFuncionario


class EventoCerimonialConviteSerializer(serializers.ModelSerializer):
    signup_url = serializers.CharField(read_only=True)
    qr_code_url = serializers.CharField(read_only=True)

    class Meta:
        model = EventoCerimonialConvite
        fields = [
            "id",
            "evento",
            "tipo",
            "token",
            "ativo",
            "signup_url",
            "qr_code_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "evento",
            "token",
            "created_at",
            "updated_at",
        ]


class EventoCerimonialFuncionarioSerializer(serializers.ModelSerializer):
    documento_mascarado = serializers.CharField(read_only=True)

    class Meta:
        model = EventoCerimonialFuncionario
        fields = [
            "id",
            "evento",
            "usuario",
            "nome",
            "documento",
            "documento_mascarado",
            "funcao",
            "horario_entrada",
            "horario_saida",
            "pagamento_realizado",
            "valor_pagamento",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "evento", "created_at", "updated_at"]
