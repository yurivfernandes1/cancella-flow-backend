from rest_framework import serializers

from ...models import Ocorrencia


class OcorrenciaSerializer(serializers.ModelSerializer):
    criado_por_nome = serializers.SerializerMethodField()
    respondido_por_nome = serializers.SerializerMethodField()

    class Meta:
        model = Ocorrencia
        fields = [
            "id",
            "tipo",
            "titulo",
            "descricao",
            "status",
            "criado_por",
            "criado_por_nome",
            "resposta",
            "respondido_por",
            "respondido_por_nome",
            "respondido_em",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "criado_por",
            "criado_por_nome",
            "respondido_por",
            "respondido_por_nome",
            "respondido_em",
            "created_at",
            "updated_at",
        ]

    def get_criado_por_nome(self, obj):
        if obj.criado_por:
            return obj.criado_por.full_name or obj.criado_por.username
        return None

    def get_respondido_por_nome(self, obj):
        if obj.respondido_por:
            return obj.respondido_por.full_name or obj.respondido_por.username
        return None


class OcorrenciaCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ocorrencia
        fields = ["tipo", "titulo", "descricao"]

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["criado_por"] = request.user
        return super().create(validated_data)


class OcorrenciaRespostaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ocorrencia
        fields = ["resposta", "status"]
