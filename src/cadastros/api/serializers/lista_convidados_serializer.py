from rest_framework import serializers

from ...models import ConvidadoLista, ListaConvidados


class ConvidadoListaSerializer(serializers.ModelSerializer):
    cpf_formatado = serializers.SerializerMethodField()

    class Meta:
        model = ConvidadoLista
        fields = [
            "id",
            "cpf",
            "cpf_formatado",
            "nome",
            "email",
            "qr_token",
            "entrada_confirmada",
            "entrada_em",
            "created_on",
        ]
        read_only_fields = [
            "id",
            "cpf_formatado",
            "qr_token",
            "entrada_em",
            "created_on",
        ]

    def get_cpf_formatado(self, obj):
        cpf = obj.cpf
        if len(cpf) == 11:
            return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
        return cpf


class ListaConvidadosSerializer(serializers.ModelSerializer):
    convidados = ConvidadoListaSerializer(many=True, read_only=True)
    morador_nome = serializers.SerializerMethodField()
    total_convidados = serializers.SerializerMethodField()
    local_descricao = serializers.SerializerMethodField()

    class Meta:
        model = ListaConvidados
        fields = [
            "id",
            "morador",
            "morador_nome",
            "titulo",
            "descricao",
            "data_evento",
            "ativa",
            "local_tipo",
            "espaco",
            "unidade_evento",
            "local_descricao",
            "total_convidados",
            "convidados",
            "created_on",
            "updated_on",
        ]
        read_only_fields = ["id", "morador", "created_on", "updated_on"]

    def get_morador_nome(self, obj):
        return getattr(obj.morador, "full_name", None) or obj.morador.username

    def get_total_convidados(self, obj):
        return obj.convidados.count()

    def get_local_descricao(self, obj):
        if obj.local_tipo == "espaco" and obj.espaco:
            return f"Espaço: {obj.espaco.nome}"
        if obj.local_tipo == "unidade" and obj.unidade_evento:
            return f"Unidade: {obj.unidade_evento.identificacao_completa}"
        return "Local não informado"
