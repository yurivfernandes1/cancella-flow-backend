from rest_framework import serializers

from ...models import ConvidadoLista, ListaConvidados


class ConvidadoListaSerializer(serializers.ModelSerializer):
    cpf_formatado = serializers.SerializerMethodField()

    class Meta:
        model = ConvidadoLista
        fields = ["id", "cpf", "cpf_formatado", "nome", "created_on"]
        read_only_fields = ["id", "created_on"]

    def get_cpf_formatado(self, obj):
        cpf = obj.cpf
        if len(cpf) == 11:
            return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
        return cpf


class ListaConvidadosSerializer(serializers.ModelSerializer):
    convidados = ConvidadoListaSerializer(many=True, read_only=True)
    morador_nome = serializers.SerializerMethodField()
    total_convidados = serializers.SerializerMethodField()

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
