from functools import lru_cache

import requests
from access.models import User
from rest_framework import serializers

from ...models import EventoCerimonial


def _to_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@lru_cache(maxsize=512)
def _buscar_dados_cep(cep_digits):
    if not cep_digits or len(cep_digits) != 8:
        return None
    try:
        response = requests.get(
            f"https://brasilapi.com.br/api/cep/v2/{cep_digits}", timeout=5
        )
        if response.status_code == 200:
            return response.json()
    except Exception:
        return None
    return None


class ParticipanteEventoSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "full_name", "username", "phone"]


class EventoCerimonialSerializer(serializers.ModelSerializer):
    cerimonialistas = ParticipanteEventoSerializer(many=True, read_only=True)
    organizadores = ParticipanteEventoSerializer(many=True, read_only=True)
    funcionarios = ParticipanteEventoSerializer(many=True, read_only=True)

    cerimonialistas_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
    )
    organizadores_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
    )
    funcionarios_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
    )

    logradouro = serializers.SerializerMethodField(read_only=True)
    bairro = serializers.SerializerMethodField(read_only=True)
    cidade = serializers.SerializerMethodField(read_only=True)
    estado = serializers.SerializerMethodField(read_only=True)
    endereco_completo = serializers.SerializerMethodField(read_only=True)
    imagem_url = serializers.SerializerMethodField(read_only=True)
    lista_convidados_id = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = EventoCerimonial
        fields = [
            "id",
            "nome",
            "datetime_inicio",
            "datetime_fim",
            "cep",
            "numero",
            "complemento",
            "logradouro",
            "bairro",
            "cidade",
            "estado",
            "endereco_completo",
            "numero_pessoas",
            "evento_confirmado",
            "imagem_url",
            "lista_convidados_id",
            "cerimonialistas",
            "organizadores",
            "funcionarios",
            "cerimonialistas_ids",
            "organizadores_ids",
            "funcionarios_ids",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def _normalizar_cep(self, value):
        if value is None:
            return ""
        return "".join(ch for ch in str(value) if ch.isdigit())

    def _resolver_usuarios(self, ids, grupo_nome):
        if not ids:
            return []
        usuarios = list(User.objects.filter(id__in=ids).distinct())
        ids_encontrados = {u.id for u in usuarios}
        ids_informados = set(ids)
        faltantes = ids_informados - ids_encontrados
        if faltantes:
            raise serializers.ValidationError(
                f"Usuários não encontrados para {grupo_nome}."
            )
        for usuario in usuarios:
            if not usuario.groups.filter(name__iexact=grupo_nome).exists():
                raise serializers.ValidationError(
                    f"Usuário {usuario.username} não pertence ao grupo {grupo_nome}."
                )
        return usuarios

    def validate(self, attrs):
        dt_inicio = attrs.get("datetime_inicio")
        dt_fim = attrs.get("datetime_fim")
        if dt_inicio and dt_fim and dt_fim <= dt_inicio:
            raise serializers.ValidationError(
                {
                    "datetime_fim": "A data/hora de término deve ser posterior ao início."
                }
            )

        cep = self._normalizar_cep(attrs.get("cep", self.instance.cep if self.instance else ""))
        if cep and len(cep) != 8:
            raise serializers.ValidationError(
                {"cep": "Informe um CEP válido com 8 dígitos."}
            )
        attrs["cep"] = cep

        if "evento_confirmado" in attrs:
            attrs["evento_confirmado"] = _to_bool(attrs["evento_confirmado"])

        request = self.context.get("request")
        current_user = getattr(request, "user", None)

        cerimonialistas_ids = attrs.pop("cerimonialistas_ids", None)
        organizadores_ids = attrs.pop("organizadores_ids", None)
        funcionarios_ids = attrs.pop("funcionarios_ids", None)

        if cerimonialistas_ids is not None:
            attrs["_cerimonialistas"] = self._resolver_usuarios(
                cerimonialistas_ids, "Cerimonialista"
            )
        elif not self.instance and current_user:
            attrs["_cerimonialistas"] = [current_user]

        if organizadores_ids is not None:
            attrs["_organizadores"] = self._resolver_usuarios(
                organizadores_ids, "Organizador do Evento"
            )

        if funcionarios_ids is not None:
            attrs["_funcionarios"] = self._resolver_usuarios(
                funcionarios_ids, "Recepção"
            )

        if "_cerimonialistas" in attrs and current_user:
            if not any(u.id == current_user.id for u in attrs["_cerimonialistas"]):
                attrs["_cerimonialistas"].append(current_user)

        if not self.instance and not attrs.get("_cerimonialistas"):
            raise serializers.ValidationError(
                {"cerimonialistas_ids": "Informe ao menos um cerimonialista."}
            )

        return attrs

    def create(self, validated_data):
        cerimonialistas = validated_data.pop("_cerimonialistas", [])
        organizadores = validated_data.pop("_organizadores", [])
        funcionarios = validated_data.pop("_funcionarios", [])

        evento = EventoCerimonial.objects.create(**validated_data)
        if cerimonialistas:
            evento.cerimonialistas.set(cerimonialistas)
        if organizadores:
            evento.organizadores.set(organizadores)
        if funcionarios:
            evento.funcionarios.set(funcionarios)
        return evento

    def update(self, instance, validated_data):
        cerimonialistas = validated_data.pop("_cerimonialistas", None)
        organizadores = validated_data.pop("_organizadores", None)
        funcionarios = validated_data.pop("_funcionarios", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if cerimonialistas is not None:
            instance.cerimonialistas.set(cerimonialistas)
        if organizadores is not None:
            instance.organizadores.set(organizadores)
        if funcionarios is not None:
            instance.funcionarios.set(funcionarios)

        return instance

    def _dados_cep(self, obj):
        cep = "".join(ch for ch in (obj.cep or "") if ch.isdigit())
        return _buscar_dados_cep(cep)

    def get_logradouro(self, obj):
        dados = self._dados_cep(obj)
        return (dados or {}).get("street", "")

    def get_bairro(self, obj):
        dados = self._dados_cep(obj)
        return (dados or {}).get("neighborhood", "")

    def get_cidade(self, obj):
        dados = self._dados_cep(obj)
        return (dados or {}).get("city", "")

    def get_estado(self, obj):
        dados = self._dados_cep(obj)
        return (dados or {}).get("state", "")

    def get_endereco_completo(self, obj):
        dados = self._dados_cep(obj)
        partes = []

        logradouro = (dados or {}).get("street", "")
        if logradouro:
            endereco_base = f"{logradouro}, {obj.numero}" if obj.numero else logradouro
            partes.append(endereco_base)
        elif obj.numero:
            partes.append(f"Número {obj.numero}")

        if obj.complemento:
            partes.append(obj.complemento)

        bairro = (dados or {}).get("neighborhood", "")
        if bairro:
            partes.append(bairro)

        cidade = (dados or {}).get("city", "")
        estado = (dados or {}).get("state", "")
        if cidade and estado:
            partes.append(f"{cidade} - {estado}")
        elif cidade:
            partes.append(cidade)

        cep = "".join(ch for ch in (obj.cep or "") if ch.isdigit())
        if cep:
            cep_fmt = f"{cep[:5]}-{cep[5:]}" if len(cep) == 8 else cep
            partes.append(f"CEP: {cep_fmt}")

        return ", ".join(partes)

    def get_imagem_url(self, obj):
        request = self.context.get("request")
        if not obj.imagem_db_data:
            return None
        path = f"/api/cadastros/eventos-cerimonial/{obj.id}/imagem-db/"
        if request:
            return request.build_absolute_uri(path)
        return path

    def get_lista_convidados_id(self, obj):
        lista = getattr(obj, "lista_convidados", None)
        return getattr(lista, "id", None)


class EventoCerimonialListSerializer(serializers.ModelSerializer):
    endereco_completo = serializers.SerializerMethodField(read_only=True)
    imagem_url = serializers.SerializerMethodField(read_only=True)
    lista_convidados_id = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = EventoCerimonial
        fields = [
            "id",
            "nome",
            "datetime_inicio",
            "datetime_fim",
            "endereco_completo",
            "numero_pessoas",
            "evento_confirmado",
            "imagem_url",
            "lista_convidados_id",
            "created_at",
        ]

    def get_endereco_completo(self, obj):
        return EventoCerimonialSerializer(context=self.context).get_endereco_completo(
            obj
        )

    def get_imagem_url(self, obj):
        return EventoCerimonialSerializer(context=self.context).get_imagem_url(obj)

    def get_lista_convidados_id(self, obj):
        lista = getattr(obj, "lista_convidados", None)
        return getattr(lista, "id", None)
