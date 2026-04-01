from rest_framework import serializers

from ...models import ConvidadoListaCerimonial, ListaConvidadosCerimonial


class ConvidadoListaCerimonialSerializer(serializers.ModelSerializer):
    cpf_formatado = serializers.SerializerMethodField()
    cpf_mascarado = serializers.SerializerMethodField()

    class Meta:
        model = ConvidadoListaCerimonial
        fields = [
            "id",
            "cpf",
            "cpf_formatado",
            "cpf_mascarado",
            "nome",
            "email",
            "vip",
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
        cpf = obj.cpf or ""
        if len(cpf) == 11:
            return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
        return cpf

    def get_cpf_mascarado(self, obj):
        cpf = obj.cpf or ""
        if len(cpf) == 11:
            return f"{cpf[:3]}*****{cpf[-3:]}"
        return cpf


class ListaConvidadosCerimonialSerializer(serializers.ModelSerializer):
    convidados = serializers.SerializerMethodField()
    total_convidados = serializers.SerializerMethodField()
    evento_nome = serializers.CharField(source="evento.nome", read_only=True)
    evento_confirmado = serializers.BooleanField(
        source="evento.evento_confirmado", read_only=True
    )
    endereco_evento = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ListaConvidadosCerimonial
        fields = [
            "id",
            "evento",
            "evento_nome",
            "evento_confirmado",
            "endereco_evento",
            "titulo",
            "descricao",
            "data_evento",
            "ativa",
            "total_convidados",
            "convidados",
            "created_on",
            "updated_on",
        ]
        read_only_fields = ["id", "created_on", "updated_on"]

    def get_total_convidados(self, obj):
        return obj.convidados.count()

    def get_convidados(self, obj):
        convidados = obj.convidados.all().order_by("-vip", "nome", "id")
        return ConvidadoListaCerimonialSerializer(convidados, many=True).data

    def get_endereco_evento(self, obj):
        from .evento_cerimonial_serializer import EventoCerimonialSerializer

        return EventoCerimonialSerializer().get_endereco_completo(obj.evento)
