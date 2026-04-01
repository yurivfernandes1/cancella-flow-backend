from rest_framework import serializers

from ...models import (
    EventoCerimonialConvite,
    EventoCerimonialFuncionario,
    FuncaoFesta,
)


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


class FuncaoFestaSerializer(serializers.ModelSerializer):
    class Meta:
        model = FuncaoFesta
        fields = [
            "id",
            "nome",
            "ativo",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class EventoCerimonialFuncionarioSerializer(serializers.ModelSerializer):
    documento_mascarado = serializers.CharField(read_only=True)
    funcoes = FuncaoFestaSerializer(many=True, read_only=True)
    funcoes_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        write_only=True,
        required=False,
    )
    usuario_nome = serializers.SerializerMethodField(read_only=True)
    usuario_email = serializers.SerializerMethodField(read_only=True)
    usuario_phone = serializers.SerializerMethodField(read_only=True)
    usuario_ativo = serializers.SerializerMethodField(read_only=True)

    def get_usuario_nome(self, obj):
        if not obj.usuario:
            return None
        return obj.usuario.full_name or obj.usuario.username

    def get_usuario_email(self, obj):
        if not obj.usuario:
            return None
        return obj.usuario.email

    def get_usuario_phone(self, obj):
        if not obj.usuario:
            return None
        return obj.usuario.phone

    def get_usuario_ativo(self, obj):
        if not obj.usuario:
            return None
        return bool(obj.usuario.is_active)

    def validate(self, attrs):
        funcoes_ids = attrs.pop("funcoes_ids", None)
        if funcoes_ids is not None:
            ids_ordenados = list(dict.fromkeys(funcoes_ids))
            queryset = FuncaoFesta.objects.filter(id__in=ids_ordenados)

            request = self.context.get("request")
            if request and not request.user.is_staff:
                queryset = queryset.filter(created_by=request.user)

            funcoes = list(queryset)
            encontrados = {f.id for f in funcoes}
            faltantes = [
                fid for fid in ids_ordenados if fid not in encontrados
            ]
            if faltantes:
                raise serializers.ValidationError(
                    {
                        "funcoes_ids": "Uma ou mais funções não existem ou não estão disponíveis."
                    }
                )

            attrs["_funcoes_objs"] = funcoes

        return attrs

    def _sync_funcao_legado(self, instance, funcoes):
        if not funcoes:
            funcao_legado = ""
        else:
            nomes = [str(f.nome).strip() for f in funcoes if f.nome]
            funcao_legado = ", ".join(nomes)[:100]

        if instance.funcao != funcao_legado:
            instance.funcao = funcao_legado
            instance.save(update_fields=["funcao", "updated_at"])

    def create(self, validated_data):
        funcoes = validated_data.pop("_funcoes_objs", None)
        instance = super().create(validated_data)
        if funcoes is not None:
            instance.funcoes.set(funcoes)
            self._sync_funcao_legado(instance, funcoes)
        return instance

    def update(self, instance, validated_data):
        funcoes = validated_data.pop("_funcoes_objs", None)
        instance = super().update(instance, validated_data)
        if funcoes is not None:
            instance.funcoes.set(funcoes)
            self._sync_funcao_legado(instance, funcoes)
        return instance

    class Meta:
        model = EventoCerimonialFuncionario
        fields = [
            "id",
            "evento",
            "usuario",
            "usuario_nome",
            "usuario_email",
            "usuario_phone",
            "usuario_ativo",
            "nome",
            "documento",
            "documento_mascarado",
            "is_recepcao",
            "funcao",
            "funcoes",
            "funcoes_ids",
            "horario_entrada",
            "horario_saida",
            "pagamento_realizado",
            "valor_pagamento",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "evento", "created_at", "updated_at"]
