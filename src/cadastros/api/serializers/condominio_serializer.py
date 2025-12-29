import requests
from access.models import User
from rest_framework import serializers

from ...models import Condominio


class CondominioSerializer(serializers.ModelSerializer):
    sindico_nome = serializers.SerializerMethodField(read_only=True)
    sindico_id = serializers.SerializerMethodField(read_only=True)
    endereco_completo = serializers.SerializerMethodField(read_only=True)
    logradouro = serializers.SerializerMethodField(read_only=True)
    bairro = serializers.SerializerMethodField(read_only=True)
    cidade = serializers.SerializerMethodField(read_only=True)
    estado = serializers.SerializerMethodField(read_only=True)
    logo_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Condominio
        fields = [
            "id",
            "nome",
            "cep",
            "numero",
            "complemento",
            "logradouro",
            "bairro",
            "cidade",
            "estado",
            "endereco_completo",
            "cnpj",
            "telefone",
            "logo",
            "logo_url",
            "sindico_nome",
            "sindico_id",
            "is_ativo",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "sindico_nome",
            "sindico_id",
            "endereco_completo",
            "logradouro",
            "bairro",
            "cidade",
            "estado",
            "logo_url",
        ]

    def get_logo_url(self, obj):
        """Retorna a URL completa da logo"""
        # Prioriza logo armazenada no banco (campos logo_db_* no próprio modelo)
        request = self.context.get("request")
        if getattr(obj, "logo_db_data", None):
            if request:
                return request.build_absolute_uri(
                    f"/api/cadastros/condominios/{obj.id}/logo-db/"
                )
            return f"/api/cadastros/condominios/{obj.id}/logo-db/"

        if obj.logo:
            if request:
                return request.build_absolute_uri(obj.logo.url)
            return obj.logo.url

        return None

    def _buscar_dados_cep(self, cep):
        """Busca dados do CEP na API Brasil"""
        if not cep or len(cep) != 8:
            return None

        try:
            response = requests.get(
                f"https://brasilapi.com.br/api/cep/v2/{cep}", timeout=5
            )
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass

        return None

    def get_logradouro(self, obj):
        """Retorna o logradouro buscado via API"""
        if obj.cep:
            dados = self._buscar_dados_cep(obj.cep)
            if dados:
                return dados.get("street", "")
        return ""

    def get_bairro(self, obj):
        """Retorna o bairro buscado via API"""
        if obj.cep:
            dados = self._buscar_dados_cep(obj.cep)
            if dados:
                return dados.get("neighborhood", "")
        return ""

    def get_cidade(self, obj):
        """Retorna a cidade buscada via API"""
        if obj.cep:
            dados = self._buscar_dados_cep(obj.cep)
            if dados:
                return dados.get("city", "")
        return ""

    def get_estado(self, obj):
        """Retorna o estado buscado via API"""
        if obj.cep:
            dados = self._buscar_dados_cep(obj.cep)
            if dados:
                return dados.get("state", "")
        return ""

    def get_endereco_completo(self, obj):
        """Monta o endereço completo a partir dos dados do CEP"""
        if not obj.cep:
            return ""

        dados = self._buscar_dados_cep(obj.cep)
        if not dados:
            return f"CEP: {obj.cep}"

        partes = []

        # Logradouro + número
        logradouro = dados.get("street", "")
        if logradouro:
            endereco_base = (
                f"{logradouro}, {obj.numero}" if obj.numero else logradouro
            )
            partes.append(endereco_base)

        # Complemento
        if obj.complemento:
            partes.append(obj.complemento)

        # Bairro
        bairro = dados.get("neighborhood", "")
        if bairro:
            partes.append(bairro)

        # Cidade - Estado
        cidade = dados.get("city", "")
        estado = dados.get("state", "")
        if cidade and estado:
            partes.append(f"{cidade} - {estado}")
        elif cidade:
            partes.append(cidade)

        # CEP
        cep_formatado = (
            f"{obj.cep[:5]}-{obj.cep[5:]}" if len(obj.cep) == 8 else obj.cep
        )
        partes.append(f"CEP: {cep_formatado}")

        return ", ".join(partes)

    def get_sindico_nome(self, obj):
        # Busca o síndico através do relacionamento reverso
        sindico = obj.usuarios.filter(groups__name="Síndicos").first()
        if sindico:
            return (
                sindico.full_name
                if sindico.full_name
                else f"{sindico.first_name} {sindico.last_name}".strip()
            )
        return None

    def get_sindico_id(self, obj):
        # Busca o síndico através do relacionamento reverso
        sindico = obj.usuarios.filter(groups__name="Síndicos").first()
        return sindico.id if sindico else None

    def validate_cnpj(self, value):
        if value:
            # Remove todos os caracteres não numéricos
            return "".join(filter(str.isdigit, value))
        return value

    def validate_telefone(self, value):
        if value:
            # Remove todos os caracteres não numéricos
            return "".join(filter(str.isdigit, value))
        return value

    def validate_sindico_id(self, value):
        if value:
            try:
                sindico = User.objects.get(id=value)
                if not sindico.groups.filter(name="Síndicos").exists():
                    raise serializers.ValidationError(
                        "O usuário selecionado não é um síndico."
                    )
                return value
            except User.DoesNotExist:
                raise serializers.ValidationError("Síndico não encontrado.")
        return value


class CondominioListSerializer(serializers.ModelSerializer):
    sindico_nome = serializers.SerializerMethodField(read_only=True)
    endereco_completo = serializers.SerializerMethodField(read_only=True)
    logo_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Condominio
        fields = [
            "id",
            "nome",
            "cep",
            "numero",
            "complemento",
            "endereco_completo",
            "cnpj",
            "telefone",
            "logo_url",
            "sindico_nome",
            "is_ativo",
        ]

    def get_logo_url(self, obj):
        """Retorna a URL completa da logo"""
        # Prioriza logo armazenada no banco (campos logo_db_* no próprio modelo)
        request = self.context.get("request")
        if getattr(obj, "logo_db_data", None):
            if request:
                return request.build_absolute_uri(
                    f"/api/cadastros/condominios/{obj.id}/logo-db/"
                )
            return f"/api/cadastros/condominios/{obj.id}/logo-db/"

        if obj.logo:
            if request:
                return request.build_absolute_uri(obj.logo.url)
            return obj.logo.url

        return None

    def _buscar_dados_cep(self, cep):
        """Busca dados do CEP na API Brasil"""
        if not cep or len(cep) != 8:
            return None

        try:
            response = requests.get(
                f"https://brasilapi.com.br/api/cep/v2/{cep}", timeout=5
            )
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass

        return None

    def get_endereco_completo(self, obj):
        """Monta o endereço completo a partir dos dados do CEP"""
        if not obj.cep:
            return ""

        dados = self._buscar_dados_cep(obj.cep)
        if not dados:
            return f"CEP: {obj.cep}"

        partes = []

        # Logradouro + número
        logradouro = dados.get("street", "")
        if logradouro:
            endereco_base = (
                f"{logradouro}, {obj.numero}" if obj.numero else logradouro
            )
            partes.append(endereco_base)

        # Complemento
        if obj.complemento:
            partes.append(obj.complemento)

        # Bairro
        bairro = dados.get("neighborhood", "")
        if bairro:
            partes.append(bairro)

        # Cidade - Estado
        cidade = dados.get("city", "")
        estado = dados.get("state", "")
        if cidade and estado:
            partes.append(f"{cidade} - {estado}")
        elif cidade:
            partes.append(cidade)

        # CEP
        cep_formatado = (
            f"{obj.cep[:5]}-{obj.cep[5:]}" if len(obj.cep) == 8 else obj.cep
        )
        partes.append(f"CEP: {cep_formatado}")

        return ", ".join(partes)

    def get_sindico_nome(self, obj):
        # Busca o síndico através do relacionamento reverso
        sindico = obj.usuarios.filter(groups__name="Síndicos").first()
        if sindico:
            return (
                sindico.full_name
                if sindico.full_name
                else f"{sindico.first_name} {sindico.last_name}".strip()
            )
        return None
