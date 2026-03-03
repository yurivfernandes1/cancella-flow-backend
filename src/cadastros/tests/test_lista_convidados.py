"""
Testes para o módulo de Lista de Convidados / QR Code.

Cobre:
  - CRUD de listas (criação, leitura, atualização, exclusão)
  - Permissões por grupo (Moradores / Portaria / Síndicos / sem grupo)
  - Adição e remoção de convidados
  - Confirmação de entrada manual (toggle)
  - Confirmação de entrada por QR Code (token válido / já usado / inválido)
  - Envio de e-mail via Resend (mockado para não fazer chamadas reais)
  - Filtro "somente hoje" (data_evento)
"""

import uuid
from datetime import date
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from cadastros.models import ConvidadoLista, ListaConvidados

User = get_user_model()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# Contador global para gerar CPFs únicos a cada chamada
_cpf_counter = [0]


def _next_cpf():
    _cpf_counter[0] += 1
    return str(_cpf_counter[0]).zfill(11)


def _make_user(username, group_name=None, condominio=None):
    """Cria um usuário com CPF/phone únicos e o adiciona a um grupo opcional."""
    user = User.objects.create_user(
        username=username,
        password="testpass123",
        full_name=f"User {username}",
        cpf=_next_cpf(),
        phone="11999999999",
        condominio=condominio,
    )
    if group_name:
        group, _ = Group.objects.get_or_create(name=group_name)
        user.groups.add(group)
    return user


def _token(user):
    return str(RefreshToken.for_user(user).access_token)


def _auth(client, user):
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {_token(user)}")


# ---------------------------------------------------------------------------
# Fixtures base
# ---------------------------------------------------------------------------


class BaseListaTestCase(APITestCase):
    """Setup comum: morador, portaria, síndico e lista inicial."""

    def setUp(self):
        self.morador = _make_user("morador01", "Moradores")
        self.portaria = _make_user("portaria01", "Portaria")
        self.sindico = _make_user("sindico01", "Síndicos")
        self.outro_morador = _make_user("morador02", "Moradores")
        self.sem_grupo = _make_user("semgrupo01")

        self.lista = ListaConvidados.objects.create(
            morador=self.morador,
            titulo="Festa de Aniversário",
            data_evento=date.today(),
        )
        self.convidado = ConvidadoLista.objects.create(
            lista=self.lista,
            cpf="12345678901",
            nome="João Silva",
            email="joao@example.com",
        )


# ---------------------------------------------------------------------------
# 1. CRUD de Listas
# ---------------------------------------------------------------------------


class TestCriarLista(BaseListaTestCase):
    def test_morador_cria_lista_com_sucesso(self):
        _auth(self.client, self.morador)
        resp = self.client.post(
            reverse("listas-convidados"),
            {"titulo": "Churrasco", "data_evento": "2026-12-25"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["titulo"], "Churrasco")

    def test_criar_lista_sem_titulo_retorna_400(self):
        _auth(self.client, self.morador)
        resp = self.client.post(
            reverse("listas-convidados"), {}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", resp.data)

    def test_portaria_nao_pode_criar_lista(self):
        _auth(self.client, self.portaria)
        resp = self.client.post(
            reverse("listas-convidados"), {"titulo": "X"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_sem_autenticacao_retorna_401(self):
        resp = self.client.post(
            reverse("listas-convidados"), {"titulo": "X"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_criar_lista_com_tipo_espaco_sem_espaco_retorna_400(self):
        _auth(self.client, self.morador)
        resp = self.client.post(
            reverse("listas-convidados"),
            {"titulo": "Festa", "local_tipo": "espaco"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class TestLerListas(BaseListaTestCase):
    def test_morador_ve_proprias_listas(self):
        _auth(self.client, self.morador)
        resp = self.client.get(reverse("listas-convidados"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in resp.data]
        self.assertIn(self.lista.id, ids)

    def test_morador_nao_ve_listas_de_outro_morador(self):
        _auth(self.client, self.outro_morador)
        resp = self.client.get(reverse("listas-convidados"))
        ids = [item["id"] for item in resp.data]
        self.assertNotIn(self.lista.id, ids)

    def test_portaria_ve_todas_as_listas(self):
        _auth(self.client, self.portaria)
        resp = self.client.get(reverse("listas-convidados"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in resp.data]
        self.assertIn(self.lista.id, ids)

    def test_filtro_data_hoje_retorna_lista_de_hoje(self):
        _auth(self.client, self.portaria)
        hoje = date.today().isoformat()
        resp = self.client.get(
            reverse("listas-convidados"), {"data_evento": hoje}
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(len(resp.data) >= 1)
        for item in resp.data:
            self.assertEqual(item["data_evento"], hoje)

    def test_filtro_data_futura_nao_retorna_lista_de_hoje(self):
        _auth(self.client, self.portaria)
        resp = self.client.get(
            reverse("listas-convidados"), {"data_evento": "2099-12-31"}
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 0)

    def test_sem_grupo_recebe_403(self):
        _auth(self.client, self.sem_grupo)
        resp = self.client.get(reverse("listas-convidados"))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class TestAtualizarLista(BaseListaTestCase):
    def test_morador_atualiza_propria_lista(self):
        _auth(self.client, self.morador)
        resp = self.client.patch(
            reverse(
                "lista-convidados-detail", kwargs={"lista_pk": self.lista.pk}
            ),
            {"titulo": "Novo Título"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["titulo"], "Novo Título")

    def test_outro_morador_nao_pode_atualizar(self):
        _auth(self.client, self.outro_morador)
        resp = self.client.patch(
            reverse(
                "lista-convidados-detail", kwargs={"lista_pk": self.lista.pk}
            ),
            {"titulo": "Invadido"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_portaria_nao_pode_atualizar(self):
        _auth(self.client, self.portaria)
        resp = self.client.patch(
            reverse(
                "lista-convidados-detail", kwargs={"lista_pk": self.lista.pk}
            ),
            {"titulo": "X"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class TestExcluirLista(BaseListaTestCase):
    def test_morador_exclui_propria_lista(self):
        _auth(self.client, self.morador)
        resp = self.client.delete(
            reverse(
                "lista-convidados-detail", kwargs={"lista_pk": self.lista.pk}
            )
        )
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            ListaConvidados.objects.filter(pk=self.lista.pk).exists()
        )

    def test_portaria_nao_pode_excluir(self):
        _auth(self.client, self.portaria)
        resp = self.client.delete(
            reverse(
                "lista-convidados-detail", kwargs={"lista_pk": self.lista.pk}
            )
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------------
# 2. Convidados
# ---------------------------------------------------------------------------


class TestConvidados(BaseListaTestCase):
    def test_adicionar_convidado_valido(self):
        _auth(self.client, self.morador)
        resp = self.client.post(
            reverse(
                "lista-convidados-adicionar",
                kwargs={"lista_pk": self.lista.pk},
            ),
            {
                "cpf": "98765432100",
                "nome": "Maria Souza",
                "email": "maria@example.com",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["nome"], "Maria Souza")

    def test_adicionar_convidado_cpf_duplicado_retorna_400(self):
        _auth(self.client, self.morador)
        self.client.post(
            reverse(
                "lista-convidados-adicionar",
                kwargs={"lista_pk": self.lista.pk},
            ),
            {"cpf": "11122233344", "nome": "Dup Teste"},
            format="json",
        )
        resp = self.client.post(
            reverse(
                "lista-convidados-adicionar",
                kwargs={"lista_pk": self.lista.pk},
            ),
            {"cpf": "11122233344", "nome": "Dup Teste 2"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_remover_convidado(self):
        _auth(self.client, self.morador)
        resp = self.client.delete(
            reverse(
                "lista-convidados-remover",
                kwargs={
                    "lista_pk": self.lista.pk,
                    "convidado_pk": self.convidado.pk,
                },
            )
        )
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            ConvidadoLista.objects.filter(pk=self.convidado.pk).exists()
        )

    def test_convidado_tem_qr_token_unico(self):
        outro = ConvidadoLista.objects.create(
            lista=self.lista, cpf="55566677788", nome="Pedro"
        )
        self.assertNotEqual(self.convidado.qr_token, outro.qr_token)
        self.assertIsInstance(self.convidado.qr_token, uuid.UUID)


# ---------------------------------------------------------------------------
# 3. Confirmação de Entrada Manual
# ---------------------------------------------------------------------------


class TestConfirmarEntradaManual(BaseListaTestCase):
    def _url(self):
        return reverse(
            "lista-convidados-confirmar-entrada",
            kwargs={
                "lista_pk": self.lista.pk,
                "convidado_pk": self.convidado.pk,
            },
        )

    def test_portaria_confirma_entrada(self):
        _auth(self.client, self.portaria)
        resp = self.client.patch(self._url(), format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["entrada_confirmada"])
        self.assertIsNotNone(resp.data["entrada_em"])

    def test_portaria_desfaz_entrada(self):
        self.convidado.entrada_confirmada = True
        self.convidado.save()
        _auth(self.client, self.portaria)
        resp = self.client.patch(self._url(), format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["entrada_confirmada"])
        self.assertIsNone(resp.data["entrada_em"])

    def test_sindico_confirma_entrada(self):
        _auth(self.client, self.sindico)
        resp = self.client.patch(self._url(), format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["entrada_confirmada"])

    def test_morador_nao_pode_confirmar_entrada(self):
        _auth(self.client, self.morador)
        resp = self.client.patch(self._url(), format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_convidado_inexistente_retorna_404(self):
        _auth(self.client, self.portaria)
        resp = self.client.patch(
            reverse(
                "lista-convidados-confirmar-entrada",
                kwargs={"lista_pk": self.lista.pk, "convidado_pk": 99999},
            )
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


# ---------------------------------------------------------------------------
# 4. Confirmação por QR Code
# ---------------------------------------------------------------------------


class TestConfirmarPorQrCode(BaseListaTestCase):
    def _url(self):
        return reverse("lista-convidados-confirmar-por-qrcode")

    def test_portaria_confirma_por_qrcode_valido(self):
        _auth(self.client, self.portaria)
        resp = self.client.post(
            self._url(), {"token": str(self.convidado.qr_token)}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["success"])
        self.assertEqual(resp.data["convidado"]["nome"], "João Silva")
        self.convidado.refresh_from_db()
        self.assertTrue(self.convidado.entrada_confirmada)

    def test_qrcode_ja_usado_retorna_aviso(self):
        self.convidado.entrada_confirmada = True
        self.convidado.save()
        _auth(self.client, self.portaria)
        resp = self.client.post(
            self._url(), {"token": str(self.convidado.qr_token)}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("warning", resp.data)

    def test_qrcode_invalido_retorna_404(self):
        _auth(self.client, self.portaria)
        resp = self.client.post(
            self._url(), {"token": str(uuid.uuid4())}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_token_vazio_retorna_400(self):
        _auth(self.client, self.portaria)
        resp = self.client.post(self._url(), {"token": ""}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_morador_nao_pode_usar_qrcode(self):
        _auth(self.client, self.morador)
        resp = self.client.post(
            self._url(), {"token": str(self.convidado.qr_token)}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_sem_autenticacao_retorna_401(self):
        resp = self.client.post(
            self._url(), {"token": str(self.convidado.qr_token)}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ---------------------------------------------------------------------------
# 5. Envio de QR Code por E-mail
# ---------------------------------------------------------------------------


class TestEnviarQrCode(BaseListaTestCase):
    def _url(self):
        return reverse(
            "lista-convidados-enviar-qrcode",
            kwargs={
                "lista_pk": self.lista.pk,
                "convidado_pk": self.convidado.pk,
            },
        )

    @patch("resend.Emails.send")
    def test_morador_envia_qrcode_com_sucesso(self, mock_send):
        mock_send.return_value = MagicMock(id="email-id-fake")
        _auth(self.client, self.morador)
        resp = self.client.post(self._url(), format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["success"])
        # Garante que o Resend foi chamado exatamente uma vez
        mock_send.assert_called_once()

    @patch("resend.Emails.send")
    def test_email_enviado_para_endereco_correto(self, mock_send):
        mock_send.return_value = MagicMock(id="email-id-fake")
        _auth(self.client, self.morador)
        self.client.post(self._url(), format="json")
        call_args = mock_send.call_args[0][0]
        self.assertEqual(call_args["to"], ["joao@example.com"])
        self.assertIn(self.lista.titulo, call_args["subject"])

    @patch("resend.Emails.send")
    def test_convidado_sem_email_retorna_400(self, mock_send):
        self.convidado.email = ""
        self.convidado.save()
        _auth(self.client, self.morador)
        resp = self.client.post(self._url(), format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        mock_send.assert_not_called()

    @patch("resend.Emails.send", side_effect=Exception("Resend timeout"))
    def test_falha_no_resend_retorna_502(self, mock_send):
        _auth(self.client, self.morador)
        resp = self.client.post(self._url(), format="json")
        self.assertEqual(resp.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertIn("Falha ao enviar", resp.data["error"])

    def test_portaria_nao_pode_enviar_qrcode(self):
        _auth(self.client, self.portaria)
        resp = self.client.post(self._url(), format="json")
        # Portaria não é dona da lista → 404 (lista filtrada pelo morador)
        self.assertIn(
            resp.status_code,
            [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND],
        )

    def test_outro_morador_nao_pode_enviar_qrcode(self):
        _auth(self.client, self.outro_morador)
        resp = self.client.post(self._url(), format="json")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_convidado_inexistente_retorna_404(self):
        _auth(self.client, self.morador)
        resp = self.client.post(
            reverse(
                "lista-convidados-enviar-qrcode",
                kwargs={"lista_pk": self.lista.pk, "convidado_pk": 99999},
            ),
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @patch("resend.Emails.send")
    def test_html_do_email_contem_nome_do_convidado(self, mock_send):
        mock_send.return_value = MagicMock(id="x")
        _auth(self.client, self.morador)
        self.client.post(self._url(), format="json")
        html = mock_send.call_args[0][0]["html"]
        self.assertIn("João Silva", html)

    @patch("resend.Emails.send")
    def test_html_do_email_contem_titulo_da_lista(self, mock_send):
        mock_send.return_value = MagicMock(id="x")
        _auth(self.client, self.morador)
        self.client.post(self._url(), format="json")
        html = mock_send.call_args[0][0]["html"]
        self.assertIn("Festa de Aniversário", html)


# ---------------------------------------------------------------------------
# 6. Criação com convidados em bulk (POST /listas-convidados/)
# ---------------------------------------------------------------------------


class TestCriarListaComConvidados(BaseListaTestCase):
    def test_cria_lista_com_convidados_em_bulk(self):
        _auth(self.client, self.morador)
        resp = self.client.post(
            reverse("listas-convidados"),
            {
                "titulo": "Bulk Test",
                "convidados": [
                    {
                        "cpf": "11100022233",
                        "nome": "Ana",
                        "email": "ana@e.com",
                    },
                    {"cpf": "44455566677", "nome": "Beto", "email": ""},
                ],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["total_convidados"], 2)

    def test_cpfs_duplicados_no_bulk_sao_ignorados(self):
        _auth(self.client, self.morador)
        resp = self.client.post(
            reverse("listas-convidados"),
            {
                "titulo": "Dup Bulk",
                "convidados": [
                    {"cpf": "99988877766", "nome": "Dup A"},
                    {"cpf": "99988877766", "nome": "Dup B"},
                ],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["total_convidados"], 1)
