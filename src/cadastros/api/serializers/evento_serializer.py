from rest_framework import serializers

from ...models import Espaco, Evento


class EventoSerializer(serializers.ModelSerializer):
    espaco_nome = serializers.CharField(source="espaco.nome", read_only=True)
    espaco_id = serializers.IntegerField(
        write_only=True, required=False, allow_null=True
    )
    local_completo = serializers.CharField(read_only=True)
    imagem_url = serializers.SerializerMethodField()

    # Novos campos datetime
    datetime_inicio = serializers.DateTimeField(
        required=False, allow_null=True
    )
    datetime_fim = serializers.DateTimeField(required=False, allow_null=True)

    # Compat: aceitar escrita com data_evento/hora_* e expor leitura também
    data_evento = serializers.DateField(read_only=True)
    hora_inicio = serializers.TimeField(read_only=True)
    hora_fim = serializers.TimeField(read_only=True)

    class Meta:
        model = Evento
        fields = [
            "id",
            "titulo",
            "descricao",
            "espaco",
            "espaco_id",
            "espaco_nome",
            "local_texto",
            "local_completo",
            "datetime_inicio",
            "datetime_fim",
            "data_evento",
            "hora_inicio",
            "hora_fim",
            "imagem",
            "imagem_url",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "espaco",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # Preencher campos compatíveis
        if instance.datetime_inicio:
            rep["data_evento"] = instance.datetime_inicio.date()
            rep["hora_inicio"] = instance.datetime_inicio.time().strftime(
                "%H:%M:%S"
            )
        if instance.datetime_fim:
            rep["hora_fim"] = instance.datetime_fim.time().strftime("%H:%M:%S")
        return rep

    def get_imagem_url(self, obj):
        if obj.imagem:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.imagem.url)
        return None

    def validate_espaco_id(self, value):
        if value:
            try:
                espaco = Espaco.objects.get(id=value)
                if not espaco.is_active:
                    raise serializers.ValidationError(
                        "O espaço selecionado está inativo."
                    )
                return value
            except Espaco.DoesNotExist:
                raise serializers.ValidationError("Espaço não encontrado.")
        return value

    def validate(self, data):
        # Validar que pelo menos um local foi informado
        espaco_id = data.get("espaco_id")
        local_texto = data.get("local_texto")

        if not espaco_id and not local_texto:
            raise serializers.ValidationError(
                "Informe um espaço cadastrado ou descreva o local do evento."
            )

        ini = data.get("datetime_inicio")
        fim = data.get("datetime_fim")
        if ini and fim and fim <= ini:
            raise serializers.ValidationError(
                {
                    "datetime_fim": "A hora de término deve ser posterior à hora de início."
                }
            )
        return data

    def create(self, validated_data):
        espaco_id = validated_data.pop("espaco_id", None)
        if espaco_id:
            validated_data["espaco"] = Espaco.objects.get(id=espaco_id)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        espaco_id = validated_data.pop("espaco_id", None)
        if espaco_id:
            validated_data["espaco"] = Espaco.objects.get(id=espaco_id)
        elif (
            "espaco_id" in self.initial_data
            and self.initial_data["espaco_id"] is None
        ):
            validated_data["espaco"] = None
        return super().update(instance, validated_data)


class EventoListSerializer(serializers.ModelSerializer):
    local_completo = serializers.CharField(read_only=True)
    imagem_url = serializers.SerializerMethodField()
    data_evento = serializers.SerializerMethodField()
    hora_inicio = serializers.SerializerMethodField()
    hora_fim = serializers.SerializerMethodField()

    class Meta:
        model = Evento
        fields = [
            "id",
            "titulo",
            "descricao",
            "local_completo",
            "data_evento",
            "hora_inicio",
            "hora_fim",
            "imagem_url",
            "created_at",
            "datetime_inicio",
            "datetime_fim",
        ]

    def get_imagem_url(self, obj):
        if obj.imagem:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.imagem.url)
        return None

    def get_data_evento(self, obj):
        return obj.datetime_inicio.date() if obj.datetime_inicio else None

    def get_hora_inicio(self, obj):
        return (
            obj.datetime_inicio.time().strftime("%H:%M:%S")
            if obj.datetime_inicio
            else None
        )

    def get_hora_fim(self, obj):
        return (
            obj.datetime_fim.time().strftime("%H:%M:%S")
            if obj.datetime_fim
            else None
        )
